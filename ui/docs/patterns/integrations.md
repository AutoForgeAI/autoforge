# Integration Patterns Reference

## Message Queue Patterns

### Apache Kafka

#### When to Use Kafka
- High-throughput event streaming (millions of events/sec)
- Event sourcing and audit logs
- Real-time data pipelines
- Cross-service communication at scale
- Log aggregation and replay capability

#### Kafka Producer Best Practices
```typescript
const producer = kafka.producer({
  idempotent: true,                    // Exactly-once semantics
  maxInFlightRequests: 5,
  retry: {
    retries: 5,
    initialRetryTime: 100,
    maxRetryTime: 30000,
  },
});

async function publishEvent<T>(topic: string, key: string, event: T): Promise<void> {
  await producer.send({
    topic,
    messages: [{
      key,
      value: JSON.stringify(event),
      headers: {
        'event-type': event.constructor.name,
        'correlation-id': getCorrelationId(),
        'timestamp': Date.now().toString(),
      },
    }],
  });
}
```

#### Kafka Consumer Best Practices
```typescript
const consumer = kafka.consumer({
  groupId: 'order-service-consumer',
  sessionTimeout: 30000,
  heartbeatInterval: 3000,
  maxBytesPerPartition: 1048576,
  retry: { retries: 5 },
});

await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    try {
      const event = JSON.parse(message.value.toString());
      await processEvent(event);
      await consumer.commitOffsets([{
        topic, partition,
        offset: (parseInt(message.offset) + 1).toString(),
      }]);
    } catch (error) {
      await handleConsumerError(error, message);
    }
  },
});
```

### RabbitMQ

#### When to Use RabbitMQ
- Complex routing logic (topic, headers, fanout exchanges)
- Request-reply patterns
- Priority queues
- Delayed message delivery
- Lower latency requirements

#### RabbitMQ Patterns
```typescript
const channel = await connection.createConfirmChannel();
await channel.assertExchange('orders', 'topic', { durable: true });

function publishOrder(routingKey: string, order: Order): Promise<boolean> {
  return new Promise((resolve, reject) => {
    channel.publish('orders', routingKey, Buffer.from(JSON.stringify(order)), {
      persistent: true,
      contentType: 'application/json',
      correlationId: uuid(),
    }, (err) => err ? reject(err) : resolve(true));
  });
}

await channel.consume(queue, async (msg) => {
  if (!msg) return;
  try {
    const order = JSON.parse(msg.content.toString());
    await processOrder(order);
    channel.ack(msg);
  } catch (error) {
    const requeue = isTransientError(error);
    channel.nack(msg, false, requeue);
  }
}, { noAck: false });
```

### Redis Streams
```typescript
// Producer
await redis.xadd('orders:stream', '*', {
  type: 'ORDER_CREATED',
  payload: JSON.stringify(order),
  timestamp: Date.now(),
});

// Consumer Group
await redis.xgroup('CREATE', 'orders:stream', 'order-processors', '0', 'MKSTREAM');
const messages = await redis.xreadgroup(
  'GROUP', 'order-processors', 'consumer-1',
  'COUNT', 10, 'BLOCK', 5000,
  'STREAMS', 'orders:stream', '>'
);
```

## Event-Driven Patterns

### Event Schema Design
```typescript
interface IntegrationEvent {
  eventId: string;
  eventType: string;
  aggregateId: string;
  aggregateType: string;
  timestamp: string;
  version: number;
  correlationId: string;
  causationId: string;
  metadata: Record<string, string>;
  payload: unknown;
}
```

### Saga Pattern (Distributed Transactions)
```typescript
class OrderSaga {
  @OnEvent('order.created')
  async onOrderCreated(event: OrderCreatedEvent) {
    await this.paymentService.reservePayment(event.orderId, event.amount);
  }

  @OnEvent('payment.reserved')
  async onPaymentReserved(event: PaymentReservedEvent) {
    await this.inventoryService.reserveItems(event.orderId, event.items);
  }

  // Compensating transactions
  @OnEvent('payment.failed')
  async onPaymentFailed(event: PaymentFailedEvent) {
    await this.orderService.cancelOrder(event.orderId, 'Payment failed');
  }
}
```

### Outbox Pattern (Reliable Publishing)
```typescript
async function createOrderWithOutbox(order: Order): Promise<void> {
  await prisma.$transaction(async (tx) => {
    await tx.order.create({ data: order });
    await tx.outbox.create({
      data: {
        aggregateId: order.id,
        aggregateType: 'Order',
        eventType: 'OrderCreated',
        payload: JSON.stringify(order),
        createdAt: new Date(),
      },
    });
  });
}
```

## WebSocket & Real-Time Communication

### Socket.IO with Redis Adapter
```typescript
import { createAdapter } from '@socket.io/redis-adapter';
import { Server } from 'socket.io';

const io = new Server(httpServer, {
  cors: { origin: process.env.ALLOWED_ORIGINS?.split(','), credentials: true },
  adapter: createAdapter(pubClient, subClient),
  pingTimeout: 60000,
  pingInterval: 25000,
});

io.use(async (socket, next) => {
  const token = socket.handshake.auth.token;
  try {
    socket.data.user = await validateToken(token);
    next();
  } catch (err) {
    next(new Error('Authentication failed'));
  }
});

io.on('connection', (socket) => {
  socket.join(`user:${socket.data.user.id}`);
  socket.join(`tenant:${socket.data.user.tenantId}`);

  socket.on('subscribe', (resource) => {
    if (canAccess(socket.data.user, resource)) socket.join(resource);
  });
});
```

### Server-Sent Events (SSE)
```typescript
app.get('/api/events', authenticate, (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const subscriber = redis.duplicate();
  subscriber.subscribe(`user:${req.user.id}`);

  subscriber.on('message', (channel, message) => {
    const event = JSON.parse(message);
    res.write(`event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`);
  });

  req.on('close', () => {
    subscriber.unsubscribe();
    subscriber.quit();
  });
});
```

## File Upload & Cloud Storage

### S3 Presigned URLs
```typescript
async function getUploadUrl(key: string, contentType: string): Promise<{ uploadUrl: string; publicUrl: string }> {
  const command = new PutObjectCommand({
    Bucket: process.env.S3_BUCKET!,
    Key: key,
    ContentType: contentType,
  });

  const uploadUrl = await getSignedUrl(s3Client, command, { expiresIn: 3600 });
  const publicUrl = `https://${process.env.S3_BUCKET}.s3.${process.env.AWS_REGION}.amazonaws.com/${key}`;

  return { uploadUrl, publicUrl };
}
```

### Multipart Upload for Large Files
```typescript
const upload = new Upload({
  client: s3Client,
  params: { Bucket, Key: key, Body: body, ContentType: contentType },
  queueSize: 4,
  partSize: 5 * 1024 * 1024,
});

upload.on('httpUploadProgress', (progress) => {
  onProgress?.(Math.round((progress.loaded / progress.total) * 100));
});

await upload.done();
```

## Email, SMS & Push Notifications

### Email Queue with Bull
```typescript
const emailQueue = new Bull('email', process.env.REDIS_URL!);

emailQueue.process(async (job) => {
  const { type, data } = job.data;
  await sendEmail({
    to: data.email,
    subject: data.subject,
    template: templates[type],
    data: data.templateData,
  });
});

export async function queueEmail(type: string, data: Record<string, unknown>): Promise<void> {
  await emailQueue.add({ type, data }, {
    attempts: 3,
    backoff: { type: 'exponential', delay: 1000 },
  });
}
```

### Push Notifications (FCM)
```typescript
async function sendPushNotification(
  tokens: string[],
  notification: { title: string; body: string; imageUrl?: string },
  data?: Record<string, string>
): Promise<admin.messaging.BatchResponse> {
  return admin.messaging().sendEachForMulticast({
    tokens,
    notification,
    data,
    android: { priority: 'high' },
    apns: { payload: { aps: { badge: 1, sound: 'default' } } },
  });
}
```

## Background Job Processing

### BullMQ Job Queue
```typescript
const emailQueue = new Queue<EmailJobData>('email', { connection });

async function sendWelcomeEmail(userId: string, email: string) {
  await emailQueue.add('welcome', { to: email, template: 'welcome', data: { userId } }, {
    attempts: 3,
    backoff: { type: 'exponential', delay: 1000 },
    removeOnComplete: { count: 1000 },
    priority: 1,
  });
}

const emailWorker = new Worker<EmailJobData>('email', async (job) => {
  const html = await renderTemplate(job.data.template, job.data.data);
  await job.updateProgress(50);
  const result = await emailService.send({ to: job.data.to, html });
  return { messageId: result.messageId };
}, { connection, concurrency: 10 });
```

## Resilience Patterns

### Retry with Exponential Backoff
```typescript
async function withRetry<T>(fn: () => Promise<T>, options: RetryOptions): Promise<T> {
  for (let attempt = 1; attempt <= options.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === options.maxAttempts) throw error;
      let delay = Math.min(options.baseDelay * Math.pow(2, attempt - 1), options.maxDelay);
      if (options.jitter) delay = delay * (0.5 + Math.random());
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error('Unreachable');
}
```

### Circuit Breaker Pattern
```typescript
const breaker = new CircuitBreaker(makeRequest, {
  timeout: 5000,
  errorThresholdPercentage: 50,
  resetTimeout: 30000,
  volumeThreshold: 10,
});

breaker.on('open', () => logger.warn('Circuit OPEN'));
breaker.on('close', () => logger.info('Circuit CLOSED'));
breaker.fallback(() => ({ data: null, fromFallback: true }));
```

### Bulkhead Pattern (Isolation)
```typescript
const paymentBulkhead = new Bottleneck({ maxConcurrent: 10, highWater: 50 });
const inventoryBulkhead = new Bottleneck({ maxConcurrent: 20, highWater: 100 });

async function processOrder(order: Order) {
  const [paymentResult, inventoryResult] = await Promise.all([
    paymentBulkhead.schedule(() => paymentService.charge(order)),
    inventoryBulkhead.schedule(() => inventoryService.reserve(order)),
  ]);
  return { paymentResult, inventoryResult };
}
```

## Real-Time Collaboration

### Operational Transform (OT)
```typescript
class OTDocument {
  apply(op: Operation): string {
    switch (op.type) {
      case 'insert':
        this.content = this.content.slice(0, op.position) + op.text + this.content.slice(op.position);
        break;
      case 'delete':
        this.content = this.content.slice(0, op.position) + this.content.slice(op.position + op.count);
        break;
    }
    return this.content;
  }

  transform(op1: Operation, op2: Operation): Operation {
    // Transform op2 against op1
    if (op1.type === 'insert' && op1.position <= op2.position) {
      return { ...op2, position: op2.position + op1.text.length };
    }
    return op2;
  }
}
```

### Presence Awareness
```typescript
interface UserPresence {
  userId: string;
  name: string;
  color: string;
  cursor?: { line: number; column: number };
  lastSeen: Date;
}

class PresenceManager {
  async join(docId: string, user: User): Promise<UserPresence[]> {
    const presence: UserPresence = {
      userId: user.id,
      name: user.name,
      color: this.assignColor(),
      lastSeen: new Date(),
    };
    this.broadcast(docId, { type: 'user_joined', user: presence });
    return this.getPresence(docId);
  }
}
```
