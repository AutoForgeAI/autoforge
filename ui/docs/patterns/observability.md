# Observability Patterns Reference

## The Three Pillars of Observability

### 1. Metrics (Prometheus/StatsD)
```typescript
import { Counter, Histogram, Gauge, Registry } from 'prom-client';

const registry = new Registry();

// RED Metrics (Request, Error, Duration)
const httpRequestsTotal = new Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests',
  labelNames: ['method', 'path', 'status'],
  registers: [registry],
});

const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds',
  labelNames: ['method', 'path', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [registry],
});

// USE Metrics (Utilization, Saturation, Errors)
const dbConnectionsActive = new Gauge({
  name: 'db_connections_active',
  help: 'Active database connections',
  registers: [registry],
});

// Business Metrics
const ordersCreatedTotal = new Counter({
  name: 'orders_created_total',
  help: 'Total orders created',
  labelNames: ['customer_segment', 'payment_method'],
  registers: [registry],
});

// Middleware to track all requests
function metricsMiddleware(req: Request, res: Response, next: NextFunction) {
  const start = process.hrtime.bigint();

  res.on('finish', () => {
    const duration = Number(process.hrtime.bigint() - start) / 1e9;
    const labels = {
      method: req.method,
      path: req.route?.path || req.path,
      status: res.statusCode.toString(),
    };

    httpRequestsTotal.inc(labels);
    httpRequestDuration.observe(labels, duration);
  });

  next();
}
```

### 2. Logging (Structured JSON)
```typescript
import winston from 'winston';

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json(),
  ),
  defaultMeta: {
    service: 'order-service',
    version: process.env.APP_VERSION,
    environment: process.env.NODE_ENV,
  },
  transports: [
    new winston.transports.Console(),
    // Production: ship to ELK/Loki via Fluentd/Fluent Bit
  ],
});

// Structured logging with context
interface LogContext {
  requestId: string;
  userId?: string;
  orderId?: string;
  [key: string]: unknown;
}

function logWithContext(level: string, message: string, context: LogContext) {
  logger.log({
    level,
    message,
    ...context,
    timestamp: new Date().toISOString(),
  });
}

// Request logging middleware
function requestLoggingMiddleware(req: Request, res: Response, next: NextFunction) {
  const requestId = req.headers['x-request-id'] || crypto.randomUUID();
  req.requestId = requestId;

  logger.info({
    message: 'Request received',
    requestId,
    method: req.method,
    path: req.path,
    query: req.query,
    userAgent: req.headers['user-agent'],
    ip: req.ip,
  });

  const start = Date.now();
  res.on('finish', () => {
    logger.info({
      message: 'Request completed',
      requestId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration: Date.now() - start,
    });
  });

  next();
}
```

### 3. Distributed Tracing (OpenTelemetry)
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { trace, SpanStatusCode } from '@opentelemetry/api';

// Initialize OpenTelemetry SDK
const sdk = new NodeSDK({
  serviceName: 'order-service',
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4318/v1/traces',
  }),
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-http': { enabled: true },
      '@opentelemetry/instrumentation-express': { enabled: true },
      '@opentelemetry/instrumentation-pg': { enabled: true },
      '@opentelemetry/instrumentation-redis': { enabled: true },
    }),
  ],
});

sdk.start();

// Manual span creation for business logic
const tracer = trace.getTracer('order-service');

async function processOrder(orderId: string): Promise<void> {
  return tracer.startActiveSpan('processOrder', async (span) => {
    try {
      span.setAttribute('order.id', orderId);

      // Nested spans for sub-operations
      await tracer.startActiveSpan('validateOrder', async (validateSpan) => {
        await validateOrder(orderId);
        validateSpan.end();
      });

      await tracer.startActiveSpan('chargePayment', async (paymentSpan) => {
        const result = await chargePayment(orderId);
        paymentSpan.setAttribute('payment.amount', result.amount);
        paymentSpan.setAttribute('payment.method', result.method);
        paymentSpan.end();
      });

      span.setStatus({ code: SpanStatusCode.OK });
    } catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

// Context propagation for async operations
async function publishEvent(event: DomainEvent): Promise<void> {
  const currentSpan = trace.getActiveSpan();
  const spanContext = currentSpan?.spanContext();

  await kafka.send({
    topic: 'events',
    messages: [{
      value: JSON.stringify(event),
      headers: {
        // Propagate trace context to consumers
        'traceparent': spanContext
          ? `00-${spanContext.traceId}-${spanContext.spanId}-01`
          : undefined,
      },
    }],
  });
}
```

## SLO/SLI/SLA Monitoring

### Defining Service Level Indicators (SLIs)
```yaml
slis:
  availability:
    description: "Percentage of successful requests"
    query: |
      sum(rate(http_requests_total{status!~"5.."}[5m])) /
      sum(rate(http_requests_total[5m]))

  latency_p99:
    description: "99th percentile request latency"
    query: |
      histogram_quantile(0.99,
        sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
      )

  error_rate:
    description: "Percentage of failed requests"
    query: |
      sum(rate(http_requests_total{status=~"5.."}[5m])) /
      sum(rate(http_requests_total[5m]))
```

### SLO Configuration with Error Budget
```yaml
slos:
  order-service-availability:
    sli: availability
    target: 99.9  # 99.9% availability
    window: 30d   # Rolling 30-day window

  order-service-latency:
    sli: latency_p99
    target: 500   # 500ms p99 latency
    window: 30d

# Error Budget calculation
# 99.9% availability over 30 days = 43.2 minutes of allowed downtime
# Error budget = (1 - target) * window = 0.001 * 30 * 24 * 60 = 43.2 minutes
```

### Error Budget Alerting
```yaml
groups:
  - name: slo-alerts
    rules:
      # Burn rate alert - fast burn (2% of monthly budget in 1 hour)
      - alert: HighErrorBudgetBurn
        expr: |
          (
            1 - (sum(rate(http_requests_total{status!~"5.."}[1h])) /
                 sum(rate(http_requests_total[1h])))
          ) > (14.4 * 0.001)  # 14.4x burn rate
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error budget burn rate"
          description: "Burning error budget at 14.4x normal rate"

      # Slow burn (10% of monthly budget in 6 hours)
      - alert: ElevatedErrorBudgetBurn
        expr: |
          (
            1 - (sum(rate(http_requests_total{status!~"5.."}[6h])) /
                 sum(rate(http_requests_total[6h])))
          ) > (6 * 0.001)  # 6x burn rate
        for: 15m
        labels:
          severity: warning
```

## Alerting Best Practices

### Alert Hierarchy
```yaml
groups:
  - name: order-service-alerts
    rules:
      # P1: Critical - Immediate action required
      - alert: OrderServiceDown
        expr: up{job="order-service"} == 0
        for: 1m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Order service is down"
          runbook: "https://runbooks.example.com/order-service-down"

      # P1: Critical - Revenue impacting
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) /
          sum(rate(http_requests_total[5m])) > 0.05
        for: 2m
        labels:
          severity: critical
          impact: revenue
        annotations:
          summary: "Error rate above 5%"
          description: "Current error rate: {{ $value | humanizePercentage }}"

      # P2: Warning - Investigation required
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 1 second"

      # P3: Info - Awareness
      - alert: ElevatedMemoryUsage
        expr: |
          process_resident_memory_bytes /
          container_spec_memory_limit_bytes > 0.8
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Memory usage above 80%"
```

### On-Call Escalation
```yaml
routes:
  - match:
      severity: critical
    receiver: on-call-primary
    continue: true
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 4h

  - match:
      severity: warning
    receiver: on-call-secondary
    group_wait: 5m
    repeat_interval: 12h

  - match:
      severity: info
    receiver: slack-alerts
    group_wait: 30m

receivers:
  - name: on-call-primary
    pagerduty_configs:
      - service_key: <primary-service-key>
        severity: critical

  - name: slack-alerts
    slack_configs:
      - channel: '#alerts-info'
        send_resolved: true
```

## Dashboards (Grafana)

### Service Overview Dashboard
```json
{
  "title": "Order Service Overview",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [{
        "expr": "sum(rate(http_requests_total[5m])) by (status)"
      }]
    },
    {
      "title": "Error Rate (%)",
      "type": "stat",
      "targets": [{
        "expr": "sum(rate(http_requests_total{status=~'5..'}[5m])) / sum(rate(http_requests_total[5m])) * 100"
      }],
      "thresholds": [
        { "value": 0, "color": "green" },
        { "value": 1, "color": "yellow" },
        { "value": 5, "color": "red" }
      ]
    },
    {
      "title": "Latency Distribution",
      "type": "heatmap",
      "targets": [{
        "expr": "sum(rate(http_request_duration_seconds_bucket[5m])) by (le)"
      }]
    },
    {
      "title": "Active Database Connections",
      "type": "gauge",
      "targets": [{
        "expr": "db_connections_active / db_connections_max * 100"
      }]
    }
  ]
}
```

## Incident Response

### Incident Classification
| Priority | Impact | Response Time | Examples |
|----------|--------|---------------|----------|
| P0 | Complete outage | 5 minutes | All services down, data loss |
| P1 | Major feature broken | 15 minutes | Payments failing, auth down |
| P2 | Degraded performance | 1 hour | High latency, partial failures |
| P3 | Minor issue | 4 hours | Non-critical bug, cosmetic |

### Post-Mortem Template
```markdown
# Incident Post-Mortem: [Title]

## Summary
- **Duration**: [Start time] - [End time] ([X] minutes)
- **Impact**: [Number of users affected, revenue impact]
- **Root Cause**: [Brief description]

## Timeline
- HH:MM - Alert fired
- HH:MM - Engineer acknowledged
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Monitoring confirmed resolution

## Root Cause Analysis
[Detailed explanation using 5 Whys]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Add monitoring for X | @engineer | YYYY-MM-DD | TODO |
| Improve runbook for Y | @engineer | YYYY-MM-DD | TODO |

## Lessons Learned
- What went well
- What could be improved
```
