"""
Customer onboarding workflows with automated progression and verification.
"""
from enum import Enum, auto
from typing import Dict, Optional, List
from dataclasses import dataclass
import uuid
import time

class OnboardingStep(Enum):
    SIGNUP = auto()
    PAYMENT_METHOD = auto()
    SERVICE_SELECTION = auto()
    CONFIGURATION = auto()
    VERIFICATION = auto()
    COMPLETE = auto()

@dataclass
class OnboardingState:
    user_id: str
    current_step: OnboardingStep
    completed_steps: List[OnboardingStep]
    data: Dict[str, Any]
    last_updated: float
    timeout_at: Optional[float] = None

class OnboardingWorkflow:
    def __init__(self, execute_sql: Callable[[str], Dict[str, Any]]):
        self.execute_sql = execute_sql
        self.timeout_duration = 86400 * 3  # 3 days

    async def start_onboarding(self, user_id: str) -> OnboardingState:
        """Initialize new onboarding workflow."""
        state = OnboardingState(
            user_id=user_id,
            current_step=OnboardingStep.SIGNUP,
            completed_steps=[],
            data={},
            last_updated=time.time(),
            timeout_at=time.time() + self.timeout_duration
        )
        await self._save_state(state)
        return state

    async def advance_step(self, user_id: str, step_data: Dict[str, Any]) -> OnboardingState:
        """Progress to next onboarding step with validation."""
        state = await self._load_state(user_id)
        
        if state.current_step == OnboardingStep.SIGNUP:
            # Validate signup data
            if not all(k in step_data for k in ['email', 'name']):
                raise ValueError("Missing required signup fields")
            state.data.update(step_data)
            state.current_step = OnboardingStep.PAYMENT_METHOD
        
        elif state.current_step == OnboardingStep.PAYMENT_METHOD:
            # Validate payment method
            if not step_data.get('payment_method'):
                raise ValueError("Payment method required")
            state.data['payment_method'] = step_data['payment_method']
            state.current_step = OnboardingStep.SERVICE_SELECTION
        
        # ... other step validations
        
        state.completed_steps.append(state.current_step)
        state.last_updated = time.time()
        await self._save_state(state)
        return state

    async def _save_state(self, state: OnboardingState) -> None:
        """Persist onboarding state to database."""
        await self.execute_sql(
            f"""
            INSERT INTO onboarding_states (user_id, state_data)
            VALUES ('{state.user_id}', '{json.dumps({
                'current_step': state.current_step.name,
                'completed_steps': [s.name for s in state.completed_steps],
                'data': state.data,
                'timeout_at': state.timeout_at
            })}'::jsonb)
            ON CONFLICT (user_id) DO UPDATE
            SET state_data = EXCLUDED.state_data,
                updated_at = NOW()
            """
        )

    async def _load_state(self, user_id: str) -> OnboardingState:
        """Load onboarding state from database."""
        result = await self.execute_sql(
            f"SELECT state_data FROM onboarding_states WHERE user_id = '{user_id}'"
        )
        if not result.get('rows'):
            raise ValueError("Onboarding state not found")
        
        data = result['rows'][0]['state_data']
        return OnboardingState(
            user_id=user_id,
            current_step=OnboardingStep[data['current_step']],
            completed_steps=[OnboardingStep[s] for s in data['completed_steps']],
            data=data['data'],
            last_updated=time.time(),
            timeout_at=data.get('timeout_at')
        )
