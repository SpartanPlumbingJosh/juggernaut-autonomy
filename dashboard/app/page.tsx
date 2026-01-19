/**
 * JUGGERNAUT Executive Dashboard - Phase 7.1
 * Main dashboard page with all executive views
 */

'use client';

import React, { useState, useEffect } from 'react';
import useSWR from 'swr';
import { format, formatDistanceToNow } from 'date-fns';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Users,
  Activity,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Bell,
  Settings,
  Zap
} from 'lucide-react';

// API Configuration
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

// Fetcher for SWR
const fetcher = async (url: string) => {
  const res = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    }
  });
  if (!res.ok) throw new Error('Failed to fetch');
  return res.json();
};

// ============================================================
// METRIC CARD COMPONENT
// ============================================================

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  color?: 'green' | 'red' | 'blue' | 'yellow' | 'purple';
}

function MetricCard({ title, value, subtitle, icon: Icon, trend, trendValue, color = 'blue' }: MetricCardProps) {
  const colorClasses = {
    green: 'bg-green-50 text-green-600 border-green-200',
    red: 'bg-red-50 text-red-600 border-red-200',
    blue: 'bg-blue-50 text-blue-600 border-blue-200',
    yellow: 'bg-yellow-50 text-yellow-600 border-yellow-200',
    purple: 'bg-purple-50 text-purple-600 border-purple-200'
  };

  return (
    <div className={`rounded-lg border p-6 ${colorClasses[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-70">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-sm mt-1 opacity-70">{subtitle}</p>}
          {trend && trendValue && (
            <div className="flex items-center mt-2 text-sm">
              {trend === 'up' ? (
                <TrendingUp className="w-4 h-4 mr-1 text-green-500" />
              ) : trend === 'down' ? (
                <TrendingDown className="w-4 h-4 mr-1 text-red-500" />
              ) : null}
              <span className={trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : ''}>
                {trendValue}
              </span>
            </div>
          )}
        </div>
        <Icon className="w-12 h-12 opacity-30" />
      </div>
    </div>
  );
}

// ============================================================
// SECTION HEADER COMPONENT
// ============================================================

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

function SectionHeader({ title, subtitle, action }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">{title}</h2>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// ============================================================
// STATUS BADGE COMPONENT
// ============================================================

function StatusBadge({ status }: { status: string }) {
  const statusColors: Record<string, string> = {
    online: 'bg-green-100 text-green-800',
    offline: 'bg-gray-100 text-gray-800',
    busy: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    pending: 'bg-yellow-100 text-yellow-800',
    active: 'bg-blue-100 text-blue-800',
    blocked: 'bg-red-100 text-red-800'
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  );
}

// ============================================================
// OVERVIEW SECTION
// ============================================================

function OverviewSection({ data }: { data: any }) {
  if (!data) return <div className="animate-pulse bg-gray-200 h-48 rounded-lg" />;

  const revenue = data.revenue?.net_30d || 0;
  const costs = data.costs?.total_30d || 0;
  const profit = data.profit_loss?.net_30d || 0;
  const isProfitable = data.profit_loss?.profitable || false;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <MetricCard
        title="Revenue (30d)"
        value={`$${revenue.toLocaleString()}`}
        subtitle={`${data.revenue?.transaction_count || 0} transactions`}
        icon={DollarSign}
        color="green"
      />
      <MetricCard
        title="Costs (30d)"
        value={`$${costs.toLocaleString()}`}
        icon={TrendingDown}
        color="red"
      />
      <MetricCard
        title="Net Profit"
        value={`$${profit.toLocaleString()}`}
        subtitle={isProfitable ? 'Profitable!' : 'Not yet profitable'}
        icon={isProfitable ? TrendingUp : TrendingDown}
        color={isProfitable ? 'green' : 'red'}
      />
      <MetricCard
        title="Active Agents"
        value={data.agents?.online || 0}
        subtitle={`${data.agents?.total || 0} total`}
        icon={Users}
        color="blue"
      />
    </div>
  );
}

// ============================================================
// AGENT HEALTH SECTION
// ============================================================

function AgentHealthSection({ data }: { data: any }) {
  if (!data?.agents) return <div className="animate-pulse bg-gray-200 h-48 rounded-lg" />;

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader title="Agent Health" subtitle={`${data.summary?.total_agents || 0} agents registered`} />
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-sm text-gray-500 border-b">
              <th className="pb-3 font-medium">Agent</th>
              <th className="pb-3 font-medium">Status</th>
              <th className="pb-3 font-medium">Success Rate</th>
              <th className="pb-3 font-medium">24h Activity</th>
              <th className="pb-3 font-medium">Last Heartbeat</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.agents.map((agent: any) => (
              <tr key={agent.worker_id} className="text-sm">
                <td className="py-3 font-medium">{agent.worker_id}</td>
                <td className="py-3">
                  <StatusBadge status={agent.status} />
                </td>
                <td className="py-3">
                  <span className={agent.success_rate >= 90 ? 'text-green-600' : agent.success_rate >= 70 ? 'text-yellow-600' : 'text-red-600'}>
                    {agent.success_rate}%
                  </span>
                </td>
                <td className="py-3">
                  <span className="text-green-600">{agent.activity_24h?.completed || 0}</span>
                  {' / '}
                  <span className="text-red-600">{agent.activity_24h?.failed || 0}</span>
                </td>
                <td className="py-3 text-gray-500">
                  {agent.last_heartbeat ? (
                    <span className={agent.heartbeat_stale ? 'text-red-500' : ''}>
                      {formatDistanceToNow(new Date(agent.last_heartbeat), { addSuffix: true })}
                    </span>
                  ) : (
                    'Never'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// EXPERIMENT STATUS SECTION
// ============================================================

function ExperimentSection({ data }: { data: any }) {
  if (!data?.experiments) return <div className="animate-pulse bg-gray-200 h-48 rounded-lg" />;

  const running = data.experiments.filter((e: any) => e.status === 'running');
  const completed = data.experiments.filter((e: any) => e.status === 'completed');

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader 
        title="Experiments" 
        subtitle={`${running.length} running, ${completed.length} completed`}
      />
      
      <div className="space-y-4">
        {data.experiments.slice(0, 5).map((exp: any) => (
          <div key={exp.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-medium">{exp.name}</h3>
                <StatusBadge status={exp.status} />
              </div>
              <p className="text-sm text-gray-500 mt-1 truncate">{exp.hypothesis}</p>
            </div>
            <div className="text-right ml-4">
              <p className="font-medium">
                <span className={exp.roi >= 0 ? 'text-green-600' : 'text-red-600'}>
                  {exp.roi >= 0 ? '+' : ''}{exp.roi.toFixed(1)}% ROI
                </span>
              </p>
              <p className="text-sm text-gray-500">
                ${exp.revenue.toFixed(2)} rev / ${exp.spent.toFixed(2)} cost
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// GOAL PROGRESS SECTION
// ============================================================

function GoalProgressSection({ data }: { data: any }) {
  if (!data?.goals) return <div className="animate-pulse bg-gray-200 h-48 rounded-lg" />;

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader 
        title="Goal Progress" 
        subtitle={`${data.summary?.average_progress?.toFixed(0)}% average progress`}
      />
      
      <div className="space-y-4">
        {data.goals.slice(0, 5).map((goal: any) => (
          <div key={goal.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-gray-400" />
                <span className="font-medium">{goal.title}</span>
                <StatusBadge status={goal.status} />
              </div>
              <span className="text-sm font-medium">{goal.progress}%</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${Math.min(goal.progress, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-gray-500">
              <span>{goal.tasks_completed}/{goal.task_count} tasks</span>
              {goal.deadline && (
                <span>Due: {format(new Date(goal.deadline), 'MMM d')}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// PENDING APPROVALS SECTION
// ============================================================

function PendingApprovalsSection({ data }: { data: any }) {
  if (!data?.approvals) return <div className="animate-pulse bg-gray-200 h-32 rounded-lg" />;

  if (data.count === 0) {
    return (
      <div className="bg-white rounded-lg border p-6">
        <SectionHeader title="Pending Approvals" />
        <div className="text-center py-8 text-gray-500">
          <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
          <p>No pending approvals</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader 
        title="Pending Approvals" 
        subtitle={`${data.count} awaiting review`}
      />
      
      <div className="space-y-3">
        {data.approvals.slice(0, 5).map((approval: any) => (
          <div 
            key={approval.id} 
            className={`p-4 rounded-lg border ${approval.is_expired ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200'}`}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <AlertTriangle className={`w-4 h-4 ${approval.is_expired ? 'text-red-500' : 'text-yellow-500'}`} />
                  <span className="font-medium">{approval.action_type}</span>
                  {approval.is_expired && <span className="text-xs text-red-600 font-medium">EXPIRED</span>}
                </div>
                <p className="text-sm text-gray-600 mt-1">{approval.reason}</p>
                <p className="text-xs text-gray-500 mt-1">From: {approval.worker_id}</p>
              </div>
              <div className="flex gap-2">
                <button className="px-3 py-1 bg-green-500 text-white text-sm rounded hover:bg-green-600">
                  Approve
                </button>
                <button className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600">
                  Reject
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// SYSTEM ALERTS SECTION
// ============================================================

function SystemAlertsSection({ data }: { data: any }) {
  if (!data?.alerts) return <div className="animate-pulse bg-gray-200 h-32 rounded-lg" />;

  const severityIcons: Record<string, React.ElementType> = {
    critical: XCircle,
    error: AlertTriangle,
    warning: Bell,
    info: Activity
  };

  const severityColors: Record<string, string> = {
    critical: 'text-purple-500 bg-purple-50',
    error: 'text-red-500 bg-red-50',
    warning: 'text-yellow-500 bg-yellow-50',
    info: 'text-blue-500 bg-blue-50'
  };

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader 
        title="System Alerts" 
        subtitle={`${data.unacknowledged} unacknowledged`}
      />
      
      <div className="space-y-2">
        {data.alerts.slice(0, 5).map((alert: any) => {
          const Icon = severityIcons[alert.severity] || Activity;
          return (
            <div 
              key={alert.id}
              className={`p-3 rounded-lg flex items-start gap-3 ${severityColors[alert.severity] || 'bg-gray-50'}`}
            >
              <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{alert.alert_type}</p>
                <p className="text-sm text-gray-600 truncate">{alert.message}</p>
              </div>
              <span className="text-xs text-gray-500 flex-shrink-0">
                {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// TASK QUEUE SECTION
// ============================================================

function TaskQueueSection({ data }: { data: any }) {
  if (!data?.tasks) return <div className="animate-pulse bg-gray-200 h-48 rounded-lg" />;

  const priorityColors: Record<string, string> = {
    critical: 'bg-purple-100 text-purple-800 border-purple-200',
    high: 'bg-red-100 text-red-800 border-red-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    low: 'bg-gray-100 text-gray-800 border-gray-200'
  };

  return (
    <div className="bg-white rounded-lg border p-6">
      <SectionHeader 
        title="Task Queue" 
        subtitle={`${data.pending || 0} pending, ${data.in_progress || 0} in progress, ${data.total || 0} total`}
      />
      
      {/* Task counts */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        <div className="text-center p-2 bg-yellow-50 rounded">
          <p className="text-lg font-bold text-yellow-600">{data.pending || 0}</p>
          <p className="text-xs text-yellow-700">Pending</p>
        </div>
        <div className="text-center p-2 bg-blue-50 rounded">
          <p className="text-lg font-bold text-blue-600">{data.in_progress || 0}</p>
          <p className="text-xs text-blue-700">In Progress</p>
        </div>
        <div className="text-center p-2 bg-green-50 rounded">
          <p className="text-lg font-bold text-green-600">{data.completed || 0}</p>
          <p className="text-xs text-green-700">Completed</p>
        </div>
        <div className="text-center p-2 bg-red-50 rounded">
          <p className="text-lg font-bold text-red-600">{data.failed || 0}</p>
          <p className="text-xs text-red-700">Failed</p>
        </div>
      </div>

      {/* Task list */}
      <div className="space-y-3">
        {data.tasks.slice(0, 10).map((task: any) => (
          <div 
            key={task.id} 
            className={`p-3 rounded-lg border ${priorityColors[task.priority] || 'bg-gray-50 border-gray-200'}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Clock className="w-4 h-4 flex-shrink-0" />
                  <span className="font-medium text-sm truncate">{task.title}</span>
                  <StatusBadge status={task.status} />
                  <span className="text-xs px-2 py-0.5 rounded bg-white/50">{task.task_type}</span>
                </div>
                {task.description && (
                  <p className="text-xs text-gray-600 mt-1 line-clamp-2">{task.description.substring(0, 100)}...</p>
                )}
                {task.assigned_worker && (
                  <p className="text-xs text-gray-500 mt-1">Assigned: {task.assigned_worker}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {data.tasks.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-500" />
          <p>No tasks in queue</p>
        </div>
      )}
    </div>
  );
}


// ============================================================
// MAIN DASHBOARD COMPONENT
// ============================================================

export default function Dashboard() {
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch all dashboard data
  const { data: overview, error: overviewError } = useSWR(
    `${API_BASE}/v1/overview?k=${refreshKey}`,
    fetcher,
    { refreshInterval: 30000 }
  );

  const { data: agentHealth } = useSWR(
    `${API_BASE}/v1/agent_health?k=${refreshKey}`,
    fetcher,
    { refreshInterval: 30000 }
  );

  const { data: experiments } = useSWR(
    `${API_BASE}/v1/experiment_status?k=${refreshKey}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: goals } = useSWR(
    `${API_BASE}/v1/goal_progress?k=${refreshKey}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  const { data: approvals } = useSWR(
    `${API_BASE}/v1/pending_approvals?k=${refreshKey}`,
    fetcher,
    { refreshInterval: 15000 }
  );

  const { data: alerts } = useSWR(
    `${API_BASE}/v1/system_alerts?limit=10&k=${refreshKey}`,
    fetcher,
    { refreshInterval: 15000 }
  );

  const { data: tasks } = useSWR(
    `${API_BASE}/v1/tasks?limit=20&k=${refreshKey}`,
    fetcher,
    { refreshInterval: 30000 }
  );

  const handleRefresh = () => setRefreshKey(k => k + 1);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">JUGGERNAUT</h1>
                <p className="text-sm text-gray-500">Executive Dashboard</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={handleRefresh}
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                title="Refresh data"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
              <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                <Bell className="w-5 h-5" />
              </button>
              <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Overview Section */}
        <section>
          <OverviewSection data={overview} />
        </section>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column */}
          <div className="space-y-8">
            <AgentHealthSection data={agentHealth} />
            <GoalProgressSection data={goals} />
          </div>

          {/* Right Column */}
          <div className="space-y-8">
            <ExperimentSection data={experiments} />
            <PendingApprovalsSection data={approvals} />
            <SystemAlertsSection data={alerts} />
            <TaskQueueSection data={tasks} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white mt-8">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center text-sm text-gray-500">
          JUGGERNAUT Dashboard v1.0 | Last updated: {new Date().toLocaleString()}
        </div>
      </footer>
    </div>
  );
}
