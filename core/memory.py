"""
Memory system for JUGGERNAUT using pgvector for semantic search.

This module provides a hierarchical memory system with working, episodic, and semantic
memory types. It uses pgvector for efficient semantic search and supports memory
consolidation, decay, and sharing between agents.

Usage:
    from core.memory import MemoryService
    
    memory_service = MemoryService(embedding_client)
    
    # Store a memory
    memory_id = await memory_service.store_memory(
        worker_id="EXECUTOR",
        content="The customer reported an issue with the checkout flow",
        memory_type="episodic",
        source_type="conversation",
        source_id="123",
        importance=0.8,
        tags=["customer", "checkout", "bug"]
    )
    
    # Recall relevant memories
    memories = await memory_service.recall(
        worker_id="EXECUTOR",
        query="checkout problems",
        memory_types=["episodic", "semantic"],
        limit=5,
        min_similarity=0.7
    )
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from .database import query_db

logger = logging.getLogger(__name__)

class MemoryError(Exception):
    """Exception raised for errors in the memory module."""
    pass

class MemoryService:
    """Service for managing agent memories with pgvector."""
    
    def __init__(self, embedding_client):
        """
        Initialize the memory service.
        
        Args:
            embedding_client: Client for generating embeddings
        """
        self.embedding_client = embedding_client
    
    async def store_memory(
        self,
        worker_id: str,
        content: str,
        memory_type: str = "episodic",
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None,
        parent_memory_id: Optional[str] = None,
        related_memories: Optional[List[str]] = None,
        expires_at: Optional[str] = None
    ) -> str:
        """
        Store a new memory with embedding.
        
        Args:
            worker_id: ID of the worker storing the memory
            content: Memory content
            memory_type: Type of memory (working, episodic, semantic, procedural)
            source_type: Optional source type (task, conversation, observation, inference)
            source_id: Optional source ID
            importance: Importance score (0.0 to 1.0)
            confidence: Confidence score (0.0 to 1.0)
            tags: Optional list of tags
            parent_memory_id: Optional parent memory ID
            related_memories: Optional list of related memory IDs
            expires_at: Optional expiration timestamp (ISO format)
            
        Returns:
            ID of the created memory
            
        Raises:
            MemoryError: If memory creation fails
        """
        try:
            # Generate embedding
            embedding = await self.embedding_client.embed(content)
            
            # Generate summary for long content
            summary = None
            if len(content) > 500:
                summary = await self._generate_summary(content)
            
            # Convert UUID strings to UUIDs
            source_id_param = self._parse_uuid(source_id)
            parent_memory_id_param = self._parse_uuid(parent_memory_id)
            related_memories_param = self._parse_uuid_list(related_memories)
            
            # Insert memory
            result = await query_db(
                """
                INSERT INTO agent_memories (
                    worker_id, content, summary, embedding, memory_type,
                    source_type, source_id, importance_score, confidence_score,
                    parent_memory_id, related_memories, tags, expires_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                )
                RETURNING id
                """,
                [
                    worker_id, content, summary, embedding, memory_type,
                    source_type, source_id_param, importance, confidence,
                    parent_memory_id_param, related_memories_param, tags,
                    expires_at
                ]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                raise MemoryError("Failed to store memory")
            
            memory_id = str(result["rows"][0]["id"])
            logger.info(f"Memory stored: {memory_id} for worker {worker_id}")
            
            return memory_id
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise MemoryError(f"Failed to store memory: {e}")
    
    async def recall(
        self,
        worker_id: str,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Recall relevant memories using semantic search.
        
        Args:
            worker_id: ID of the worker recalling memories
            query: Query string
            memory_types: Optional list of memory types to filter by
            limit: Maximum number of memories to return
            min_similarity: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryError: If recall fails
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.embed(query)
            
            # Update access counts in a separate query to avoid affecting search results
            defer_access_update = True
            
            if memory_types:
                # Use the search_memories function with memory types filter
                result = await query_db(
                    """
                    SELECT * FROM search_memories($1, $2, $3, $4, $5)
                    """,
                    [query_embedding, worker_id, memory_types, min_similarity, limit]
                )
            else:
                # Use the search_memories function without memory types filter
                result = await query_db(
                    """
                    SELECT * FROM search_memories($1, $2, NULL, $3, $4)
                    """,
                    [query_embedding, worker_id, min_similarity, limit]
                )
            
            if not result or "rows" not in result:
                return []
            
            memories = result["rows"]
            
            # Update access counts
            if defer_access_update and memories:
                memory_ids = [m["id"] for m in memories]
                await self._update_access_counts(memory_ids)
            
            return memories
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            raise MemoryError(f"Failed to recall memories: {e}")
    
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID.
        
        Args:
            memory_id: ID of the memory to retrieve
            
        Returns:
            Memory data or None if not found
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            memory_id_param = self._parse_uuid(memory_id)
            
            result = await query_db(
                """
                SELECT * FROM agent_memories WHERE id = $1
                """,
                [memory_id_param]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return None
            
            memory = result["rows"][0]
            
            # Update access count
            await self._update_access_counts([memory_id])
            
            return memory
        except Exception as e:
            logger.error(f"Failed to get memory {memory_id}: {e}")
            raise MemoryError(f"Failed to get memory: {e}")
    
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        related_memories: Optional[List[str]] = None
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: ID of the memory to update
            content: Optional new content
            importance: Optional new importance score
            confidence: Optional new confidence score
            tags: Optional new tags
            related_memories: Optional new related memory IDs
            
        Returns:
            True if update was successful
            
        Raises:
            MemoryError: If update fails
        """
        try:
            memory_id_param = self._parse_uuid(memory_id)
            related_memories_param = self._parse_uuid_list(related_memories)
            
            # Build update fields
            update_fields = []
            params = [memory_id_param]
            param_index = 2
            
            if content is not None:
                update_fields.append(f"content = ${param_index}")
                params.append(content)
                param_index += 1
                
                # Generate new embedding
                embedding = await self.embedding_client.embed(content)
                update_fields.append(f"embedding = ${param_index}")
                params.append(embedding)
                param_index += 1
                
                # Generate new summary if content is long
                if len(content) > 500:
                    summary = await self._generate_summary(content)
                    update_fields.append(f"summary = ${param_index}")
                    params.append(summary)
                    param_index += 1
            
            if importance is not None:
                update_fields.append(f"importance_score = ${param_index}")
                params.append(importance)
                param_index += 1
            
            if confidence is not None:
                update_fields.append(f"confidence_score = ${param_index}")
                params.append(confidence)
                param_index += 1
            
            if tags is not None:
                update_fields.append(f"tags = ${param_index}")
                params.append(tags)
                param_index += 1
            
            if related_memories is not None:
                update_fields.append(f"related_memories = ${param_index}")
                params.append(related_memories_param)
                param_index += 1
            
            # Add updated_at
            update_fields.append("updated_at = NOW()")
            
            # Execute update
            if update_fields:
                result = await query_db(
                    f"""
                    UPDATE agent_memories
                    SET {", ".join(update_fields)}
                    WHERE id = $1
                    RETURNING id
                    """,
                    params
                )
                
                if not result or "rows" not in result or not result["rows"]:
                    return False
                
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}")
            raise MemoryError(f"Failed to update memory: {e}")
    
    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            MemoryError: If deletion fails
        """
        try:
            memory_id_param = self._parse_uuid(memory_id)
            
            result = await query_db(
                """
                DELETE FROM agent_memories
                WHERE id = $1
                RETURNING id
                """,
                [memory_id_param]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            raise MemoryError(f"Failed to delete memory: {e}")
    
    async def consolidate_memories(self, worker_id: str) -> List[str]:
        """
        Consolidate episodic memories into semantic knowledge.
        
        Args:
            worker_id: ID of the worker to consolidate memories for
            
        Returns:
            List of created semantic memory IDs
            
        Raises:
            MemoryError: If consolidation fails
        """
        try:
            # Find clusters of similar episodic memories
            clusters = await self._cluster_similar_memories(worker_id)
            
            consolidated_ids = []
            for cluster in clusters:
                if len(cluster) >= 3:  # Need multiple memories to consolidate
                    # Extract common knowledge
                    knowledge = await self._extract_knowledge(cluster)
                    
                    # Store as semantic memory
                    memory_id = await self.store_memory(
                        worker_id=worker_id,
                        content=knowledge["content"],
                        memory_type="semantic",
                        importance=knowledge["importance"],
                        confidence=knowledge["confidence"],
                        tags=["consolidated"] + (knowledge.get("tags") or []),
                        related_memories=[m["id"] for m in cluster]
                    )
                    
                    consolidated_ids.append(memory_id)
                    
                    # Add to knowledge base if confidence is high
                    if knowledge["confidence"] > 0.8:
                        await self._add_to_knowledge_base(knowledge)
            
            return consolidated_ids
        except Exception as e:
            logger.error(f"Failed to consolidate memories for worker {worker_id}: {e}")
            raise MemoryError(f"Failed to consolidate memories: {e}")
    
    async def share_memory(
        self,
        memory_id: str,
        from_worker: str,
        to_workers: List[str]
    ) -> List[str]:
        """
        Share a memory with other workers.
        
        Args:
            memory_id: ID of the memory to share
            from_worker: ID of the worker sharing the memory
            to_workers: List of worker IDs to share with
            
        Returns:
            List of created shared memory IDs
            
        Raises:
            MemoryError: If sharing fails
        """
        try:
            # Get the memory
            memory = await self.get_memory(memory_id)
            if not memory:
                raise MemoryError(f"Memory {memory_id} not found")
            
            # Check if the memory belongs to the sharing worker
            if memory["worker_id"] != from_worker:
                raise MemoryError(f"Memory {memory_id} does not belong to worker {from_worker}")
            
            shared_ids = []
            for worker_id in to_workers:
                # Create a new memory for the target worker
                shared_id = await self.store_memory(
                    worker_id=worker_id,
                    content=memory["content"],
                    memory_type="shared",
                    source_type="shared_memory",
                    source_id=memory_id,
                    importance=memory["importance_score"],
                    confidence=memory["confidence_score"] * 0.9,  # Slight confidence reduction
                    tags=(memory.get("tags") or []) + ["shared", f"from:{from_worker}"],
                    parent_memory_id=memory_id
                )
                
                shared_ids.append(shared_id)
            
            return shared_ids
        except Exception as e:
            logger.error(f"Failed to share memory {memory_id}: {e}")
            raise MemoryError(f"Failed to share memory: {e}")
    
    async def get_knowledge_entity(
        self,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a knowledge entity by ID.
        
        Args:
            entity_id: ID of the entity to retrieve
            
        Returns:
            Entity data or None if not found
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            entity_id_param = self._parse_uuid(entity_id)
            
            result = await query_db(
                """
                SELECT * FROM knowledge_entities WHERE id = $1
                """,
                [entity_id_param]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return None
            
            entity = result["rows"][0]
            
            # Get claims for this entity
            claims_result = await query_db(
                """
                SELECT * FROM knowledge_claims WHERE entity_id = $1
                """,
                [entity_id_param]
            )
            
            entity["claims"] = claims_result.get("rows", []) if claims_result else []
            
            # Get relations for this entity
            relations_result = await query_db(
                """
                SELECT kr.*, ke.name as related_entity_name, ke.entity_type as related_entity_type
                FROM knowledge_relations kr
                JOIN knowledge_entities ke ON kr.to_entity_id = ke.id
                WHERE kr.from_entity_id = $1
                """,
                [entity_id_param]
            )
            
            entity["relations"] = relations_result.get("rows", []) if relations_result else []
            
            return entity
        except Exception as e:
            logger.error(f"Failed to get knowledge entity {entity_id}: {e}")
            raise MemoryError(f"Failed to get knowledge entity: {e}")
    
    async def search_knowledge(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge entities using semantic search.
        
        Args:
            query: Query string
            entity_types: Optional list of entity types to filter by
            limit: Maximum number of entities to return
            min_similarity: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of relevant knowledge entities
            
        Raises:
            MemoryError: If search fails
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.embed(query)
            
            if entity_types:
                # Use the search_knowledge function with entity types filter
                result = await query_db(
                    """
                    SELECT * FROM search_knowledge($1, $2, $3, $4)
                    """,
                    [query_embedding, entity_types, min_similarity, limit]
                )
            else:
                # Use the search_knowledge function without entity types filter
                result = await query_db(
                    """
                    SELECT * FROM search_knowledge($1, NULL, $2, $3)
                    """,
                    [query_embedding, min_similarity, limit]
                )
            
            if not result or "rows" not in result:
                return []
            
            return result["rows"]
        except Exception as e:
            logger.error(f"Failed to search knowledge: {e}")
            raise MemoryError(f"Failed to search knowledge: {e}")
    
    async def _update_access_counts(self, memory_ids: List[str]) -> None:
        """
        Update access counts for memories.
        
        Args:
            memory_ids: List of memory IDs to update
        """
        if not memory_ids:
            return
        
        try:
            memory_ids_param = [self._parse_uuid(mid) for mid in memory_ids]
            
            await query_db(
                """
                UPDATE agent_memories
                SET access_count = access_count + 1,
                    last_accessed_at = NOW()
                WHERE id = ANY($1)
                """,
                [memory_ids_param]
            )
        except Exception as e:
            logger.warning(f"Failed to update access counts: {e}")
    
    async def _generate_summary(self, content: str) -> str:
        """
        Generate a summary for long content.
        
        Args:
            content: Content to summarize
            
        Returns:
            Summary text
        """
        # For now, just truncate to first 100 characters
        # In a real implementation, this would use an LLM to generate a summary
        return content[:100] + "..." if len(content) > 100 else content
    
    async def _cluster_similar_memories(self, worker_id: str) -> List[List[Dict[str, Any]]]:
        """
        Cluster similar episodic memories.
        
        Args:
            worker_id: Worker ID to cluster memories for
            
        Returns:
            List of memory clusters
        """
        # This is a simplified implementation
        # In a real implementation, this would use a clustering algorithm
        try:
            # Get recent episodic memories
            result = await query_db(
                """
                SELECT * FROM agent_memories
                WHERE worker_id = $1 AND memory_type = 'episodic'
                ORDER BY created_at DESC
                LIMIT 100
                """,
                [worker_id]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return []
            
            # For simplicity, just group by tags
            memories = result["rows"]
            clusters = {}
            
            for memory in memories:
                tags = memory.get("tags") or []
                if not tags:
                    continue
                
                # Use the first tag as the cluster key
                key = tags[0] if tags else "uncategorized"
                
                if key not in clusters:
                    clusters[key] = []
                
                clusters[key].append(memory)
            
            # Convert to list of clusters
            return list(clusters.values())
        except Exception as e:
            logger.warning(f"Failed to cluster memories: {e}")
            return []
    
    async def _extract_knowledge(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract common knowledge from a cluster of memories.
        
        Args:
            memories: List of memories in the cluster
            
        Returns:
            Extracted knowledge
        """
        # This is a simplified implementation
        # In a real implementation, this would use an LLM to extract knowledge
        
        # For now, just concatenate the first 3 memories
        content = "\n\n".join([m["content"] for m in memories[:3]])
        
        # Collect all tags
        all_tags = []
        for memory in memories:
            tags = memory.get("tags") or []
            all_tags.extend(tags)
        
        # Remove duplicates
        unique_tags = list(set(all_tags))
        
        # Calculate average importance and confidence
        avg_importance = sum([m.get("importance_score", 0.5) for m in memories]) / len(memories)
        avg_confidence = sum([m.get("confidence_score", 1.0) for m in memories]) / len(memories)
        
        return {
            "content": f"Consolidated knowledge: {content}",
            "importance": avg_importance,
            "confidence": avg_confidence,
            "tags": unique_tags
        }
    
    async def _add_to_knowledge_base(self, knowledge: Dict[str, Any]) -> Optional[str]:
        """
        Add extracted knowledge to the knowledge base.
        
        Args:
            knowledge: Extracted knowledge
            
        Returns:
            ID of the created knowledge entity or None if creation failed
        """
        # This is a simplified implementation
        try:
            # Generate embedding
            embedding = await self.embedding_client.embed(knowledge["content"])
            
            # Extract entity name from content
            name = knowledge["content"].split(":")[1].strip()[:50] if ":" in knowledge["content"] else knowledge["content"][:50]
            
            # Insert knowledge entity
            result = await query_db(
                """
                INSERT INTO knowledge_entities (
                    entity_type, name, description, embedding,
                    confidence_score, verified
                ) VALUES (
                    $1, $2, $3, $4, $5, $6
                )
                RETURNING id
                """,
                ["concept", name, knowledge["content"], embedding, knowledge["confidence"], False]
            )
            
            if not result or "rows" not in result or not result["rows"]:
                return None
            
            entity_id = str(result["rows"][0]["id"])
            
            # Add a claim
            await query_db(
                """
                INSERT INTO knowledge_claims (
                    entity_id, claim_type, claim_text,
                    confidence_score, consensus_level
                ) VALUES (
                    $1, $2, $3, $4, $5
                )
                """,
                [entity_id, "inference", knowledge["content"], knowledge["confidence"], "unverified"]
            )
            
            return entity_id
        except Exception as e:
            logger.warning(f"Failed to add to knowledge base: {e}")
            return None
    
    def _parse_uuid(self, uuid_str: Optional[str]) -> Optional[uuid.UUID]:
        """
        Parse a UUID string to a UUID object.
        
        Args:
            uuid_str: UUID string or None
            
        Returns:
            UUID object or None
        """
        if not uuid_str:
            return None
        
        try:
            return uuid.UUID(uuid_str)
        except ValueError:
            return None
    
    def _parse_uuid_list(self, uuid_strs: Optional[List[str]]) -> Optional[List[uuid.UUID]]:
        """
        Parse a list of UUID strings to UUID objects.
        
        Args:
            uuid_strs: List of UUID strings or None
            
        Returns:
            List of UUID objects or None
        """
        if not uuid_strs:
            return None
        
        result = []
        for uuid_str in uuid_strs:
            parsed = self._parse_uuid(uuid_str)
            if parsed:
                result.append(parsed)
        
        return result if result else None

class EmbeddingClient:
    """Client for generating embeddings."""
    
    async def embed(self, text: str) -> List[float]:
        """
        Generate an embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        # This is a placeholder implementation
        # In a real implementation, this would call an embedding API
        # For now, return a random vector of the correct dimension
        import random
        return [random.random() for _ in range(1536)]
