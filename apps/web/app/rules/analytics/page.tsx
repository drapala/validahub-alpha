'use client';

import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler,
} from 'chart.js';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useRuleAnalytics, useRuleEngineStatus } from '@/lib/rules/sse-client';
import { RuleAnalytics, RuleEngineStatus } from '@/types/rules';
import { formatNumber, formatPercentage } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Database,
  Zap,
  RefreshCw,
  Calendar,
  Download,
  Filter,
} from 'lucide-react';
import { format, subDays, subHours, subWeeks, subMonths } from 'date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler
);

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  description?: string;
  trend?: 'up' | 'down' | 'stable';
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  icon,
  description,
  trend = 'stable',
}) => {
  const getTrendIcon = () => {
    if (change === undefined) return null;
    if (trend === 'up') return <TrendingUp className="h-4 w-4 text-green-500" />;
    if (trend === 'down') return <TrendingDown className="h-4 w-4 text-red-500" />;
    return <Activity className="h-4 w-4 text-muted-foreground" />;
  };

  const getTrendColor = () => {
    if (change === undefined) return 'text-muted-foreground';
    if (trend === 'up') return 'text-green-600';
    if (trend === 'down') return 'text-red-600';
    return 'text-muted-foreground';
  };

  return (
    <Card className="metric-card">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold">{typeof value === 'number' ? formatNumber(value) : value}</p>
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="p-3 bg-primary/10 rounded-full">
              {icon}
            </div>
            {change !== undefined && (
              <div className={`flex items-center gap-1 text-sm ${getTrendColor()}`}>
                {getTrendIcon()}
                <span>{Math.abs(change)}%</span>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default function RulesAnalyticsPage() {
  const [timeRange, setTimeRange] = useState<'hour' | 'day' | 'week' | 'month'>('day');
  const [selectedRuleId, setSelectedRuleId] = useState<string>('all');
  const [analyticsData, setAnalyticsData] = useState<RuleAnalytics[]>([]);
  const [loading, setLoading] = useState(true);

  const { data: realtimeAnalytics } = useRuleAnalytics(selectedRuleId === 'all' ? undefined : selectedRuleId, timeRange);
  const { data: engineStatus, connected } = useRuleEngineStatus();

  // Simulate analytics data generation
  useEffect(() => {
    const generateMockData = () => {
      const now = new Date();
      const data: RuleAnalytics[] = [];
      
      const periods = timeRange === 'hour' ? 24 : 
                    timeRange === 'day' ? 30 : 
                    timeRange === 'week' ? 12 : 24;

      for (let i = periods; i >= 0; i--) {
        const timestamp = timeRange === 'hour' ? subHours(now, i) :
                         timeRange === 'day' ? subDays(now, i) :
                         timeRange === 'week' ? subWeeks(now, i) :
                         subMonths(now, i);

        data.push({
          rule_id: 'sample_rule',
          rule_name: 'Product Validation Rule',
          period: timeRange,
          metrics: {
            validations: Math.floor(Math.random() * 1000) + 100,
            errors: Math.floor(Math.random() * 50),
            warnings: Math.floor(Math.random() * 100),
            success_rate: 85 + Math.random() * 14,
            avg_processing_time: 150 + Math.random() * 300,
            total_rows_processed: Math.floor(Math.random() * 10000) + 1000,
          },
          timestamp: timestamp.toISOString(),
        });
      }
      
      setAnalyticsData(data);
      setLoading(false);
    };

    generateMockData();
    const interval = setInterval(generateMockData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, [timeRange]);

  // Update with real-time data
  useEffect(() => {
    if (realtimeAnalytics) {
      setAnalyticsData(prev => [...prev.slice(1), realtimeAnalytics]);
    }
  }, [realtimeAnalytics]);

  const currentMetrics = analyticsData.length > 0 ? 
    analyticsData.reduce((acc, curr) => ({
      validations: acc.validations + curr.metrics.validations,
      errors: acc.errors + curr.metrics.errors,
      warnings: acc.warnings + curr.metrics.warnings,
      success_rate: (acc.success_rate + curr.metrics.success_rate) / 2,
      avg_processing_time: (acc.avg_processing_time + curr.metrics.avg_processing_time) / 2,
      total_rows_processed: acc.total_rows_processed + curr.metrics.total_rows_processed,
    }), {
      validations: 0,
      errors: 0,
      warnings: 0,
      success_rate: 0,
      avg_processing_time: 0,
      total_rows_processed: 0,
    }) : null;

  const chartOptions = {
    responsive: true,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top' as const,
      },
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: false,
        },
      },
      y: {
        display: true,
        beginAtZero: true,
      },
    },
    maintainAspectRatio: false,
  };

  const validationTrendData = {
    labels: analyticsData.map(d => format(new Date(d.timestamp), timeRange === 'hour' ? 'HH:mm' : 'MMM dd')),
    datasets: [
      {
        label: 'Successful Validations',
        data: analyticsData.map(d => d.metrics.validations - d.metrics.errors - d.metrics.warnings),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Warnings',
        data: analyticsData.map(d => d.metrics.warnings),
        borderColor: 'rgb(234, 179, 8)',
        backgroundColor: 'rgba(234, 179, 8, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Errors',
        data: analyticsData.map(d => d.metrics.errors),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  };

  const performanceData = {
    labels: analyticsData.map(d => format(new Date(d.timestamp), timeRange === 'hour' ? 'HH:mm' : 'MMM dd')),
    datasets: [
      {
        label: 'Processing Time (ms)',
        data: analyticsData.map(d => d.metrics.avg_processing_time),
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 1,
      },
    ],
  };

  const successRateData = {
    labels: ['Success', 'Warnings', 'Errors'],
    datasets: [
      {
        data: currentMetrics ? [
          currentMetrics.validations - currentMetrics.errors - currentMetrics.warnings,
          currentMetrics.warnings,
          currentMetrics.errors,
        ] : [0, 0, 0],
        backgroundColor: [
          'rgba(34, 197, 94, 0.8)',
          'rgba(234, 179, 8, 0.8)',
          'rgba(239, 68, 68, 0.8)',
        ],
        borderColor: [
          'rgb(34, 197, 94)',
          'rgb(234, 179, 8)',
          'rgb(239, 68, 68)',
        ],
        borderWidth: 2,
      },
    ],
  };

  const exportData = () => {
    const csv = [
      ['Timestamp', 'Validations', 'Errors', 'Warnings', 'Success Rate', 'Processing Time', 'Rows Processed'],
      ...analyticsData.map(d => [
        d.timestamp,
        d.metrics.validations,
        d.metrics.errors,
        d.metrics.warnings,
        d.metrics.success_rate.toFixed(2),
        d.metrics.avg_processing_time.toFixed(0),
        d.metrics.total_rows_processed,
      ]),
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rules-analytics-${timeRange}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Rules Analytics</h1>
          <p className="text-muted-foreground">
            Real-time monitoring and performance insights for your validation rules
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <div className={`status-indicator ${connected ? 'online' : 'offline'}`}>
            <div className="pulse-dot"></div>
            {connected ? 'Live' : 'Offline'}
          </div>
          
          <div className="flex gap-1 border rounded-md">
            {(['hour', 'day', 'week', 'month'] as const).map(range => (
              <Button
                key={range}
                variant={timeRange === range ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setTimeRange(range)}
              >
                {range.charAt(0).toUpperCase() + range.slice(1)}
              </Button>
            ))}
          </div>
          
          <Button variant="outline" onClick={exportData}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Engine Status */}
      {engineStatus && (
        <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 border-blue-200 dark:border-blue-800">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <h3 className="font-semibold text-blue-900 dark:text-blue-100">Rule Engine Status</h3>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  Last heartbeat: {format(new Date(engineStatus.last_heartbeat), 'HH:mm:ss')}
                </p>
              </div>
              <div className="flex gap-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                    {engineStatus.active_validations}
                  </div>
                  <div className="text-xs text-blue-700 dark:text-blue-300">Active Jobs</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                    {engineStatus.queue_size}
                  </div>
                  <div className="text-xs text-blue-700 dark:text-blue-300">Queued</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                    {engineStatus.processing_rate}
                  </div>
                  <div className="text-xs text-blue-700 dark:text-blue-300">Rows/sec</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Key Metrics */}
      {currentMetrics && (
        <div className="analytics-grid">
          <MetricCard
            title="Total Validations"
            value={currentMetrics.validations}
            change={12.5}
            trend="up"
            icon={<Activity className="h-6 w-6 text-primary" />}
            description="Rules executed in selected period"
          />
          <MetricCard
            title="Success Rate"
            value={`${currentMetrics.success_rate.toFixed(1)}%`}
            change={2.3}
            trend="up"
            icon={<CheckCircle2 className="h-6 w-6 text-green-600" />}
            description="Percentage of successful validations"
          />
          <MetricCard
            title="Error Rate"
            value={formatPercentage(currentMetrics.errors, currentMetrics.validations)}
            change={-1.2}
            trend="down"
            icon={<XCircle className="h-6 w-6 text-red-600" />}
            description="Validation failures requiring attention"
          />
          <MetricCard
            title="Average Processing Time"
            value={`${currentMetrics.avg_processing_time.toFixed(0)}ms`}
            change={-5.8}
            trend="down"
            icon={<Clock className="h-6 w-6 text-blue-600" />}
            description="Average time per validation"
          />
          <MetricCard
            title="Rows Processed"
            value={currentMetrics.total_rows_processed}
            change={18.7}
            trend="up"
            icon={<Database className="h-6 w-6 text-purple-600" />}
            description="Total CSV rows validated"
          />
          <MetricCard
            title="Warning Rate"
            value={formatPercentage(currentMetrics.warnings, currentMetrics.validations)}
            icon={<AlertTriangle className="h-6 w-6 text-yellow-600" />}
            description="Non-critical issues detected"
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Validation Trends</CardTitle>
            <CardDescription>
              Success, warning, and error trends over time
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <Line data={validationTrendData} options={chartOptions} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Processing Performance</CardTitle>
            <CardDescription>
              Average processing time per validation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <Bar data={performanceData} options={chartOptions} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Success Distribution</CardTitle>
            <CardDescription>
              Breakdown of validation outcomes
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-80 flex items-center justify-center">
              <div className="w-64 h-64">
                <Doughnut 
                  data={successRateData} 
                  options={{
                    ...chartOptions,
                    plugins: {
                      legend: {
                        position: 'bottom' as const,
                      },
                    },
                  }} 
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Real-time Activity</CardTitle>
            <CardDescription>
              Live validation activity stream
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {analyticsData.slice(-10).reverse().map((data, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    <div>
                      <p className="text-sm font-medium">{data.rule_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {format(new Date(data.timestamp), 'HH:mm:ss')}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">
                      {data.metrics.validations} validations
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {data.metrics.success_rate.toFixed(1)}% success rate
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}