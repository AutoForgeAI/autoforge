# Testing Patterns Reference

## Testing Pyramid
- **Unit Tests (70%)**: Test individual functions/classes in isolation, < 1ms per test, no I/O
- **Integration Tests (20%)**: Test component interactions, use test containers
- **E2E Tests (10%)**: Test complete user flows against deployed environment

## Unit Test Example
```typescript
describe('Order', () => {
  describe('addItem', () => {
    it('should increase total when item added', () => {
      const order = Order.create(customerId);
      const item = OrderItem.create(productId, quantity: 2, price: 10.00);
      order.addItem(item);
      expect(order.total.amount).toBe(20.00);
      expect(order.items).toHaveLength(1);
    });

    it('should throw when adding item to completed order', () => {
      const order = Order.create(customerId);
      order.complete();
      expect(() => order.addItem(item)).toThrow(InvalidOperationError);
    });
  });
});
```

## Integration Test Example
```typescript
describe('PostgresOrderRepository', () => {
  let container: StartedPostgreSqlContainer;
  let repository: OrderRepository;

  beforeAll(async () => {
    container = await new PostgreSqlContainer().start();
    const prisma = new PrismaClient({ datasources: { db: { url: container.getConnectionUri() } } });
    await prisma.$executeRaw`...migrations...`;
    repository = new PostgresOrderRepository(prisma);
  });

  afterAll(async () => {
    await container.stop();
  });

  it('should persist and retrieve order', async () => {
    const order = OrderFactory.create();
    await repository.save(order);
    const retrieved = await repository.findById(order.id);
    expect(retrieved).toEqual(order);
  });
});
```

## Contract Testing (Pact)
```typescript
describe('Payment Service Contract', () => {
  const provider = new PactV3({
    consumer: 'OrderService',
    provider: 'PaymentService',
  });

  it('should process payment', async () => {
    await provider
      .given('customer has valid payment method')
      .uponReceiving('a payment request')
      .withRequest({
        method: 'POST',
        path: '/payments',
        body: {
          orderId: like('order-123'),
          amount: like(99.99),
          currency: 'USD',
        },
      })
      .willRespondWith({
        status: 201,
        body: {
          paymentId: like('pay-456'),
          status: 'COMPLETED',
        },
      });

    await provider.executeTest(async (mockServer) => {
      const client = new PaymentClient(mockServer.url);
      const result = await client.processPayment('order-123', 99.99);
      expect(result.status).toBe('COMPLETED');
    });
  });
});
```

## Load Testing (k6)
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 200 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const response = http.get('https://api.example.com/orders');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

## Mutation Testing (Stryker)
```json
{
  "mutator": "typescript",
  "packageManager": "npm",
  "reporters": ["html", "clear-text", "progress"],
  "testRunner": "jest",
  "coverageAnalysis": "perTest",
  "thresholds": { "high": 80, "low": 60, "break": 50 },
  "mutate": ["src/**/*.ts", "!src/**/*.test.ts"]
}
```

## Test Factories
```typescript
export const OrderFactory = {
  create(overrides: Partial<Order> = {}): Order {
    return {
      id: faker.string.uuid(),
      customerId: faker.string.uuid(),
      status: 'PENDING',
      items: [OrderItemFactory.create()],
      total: Money.fromCents(1000),
      createdAt: new Date(),
      ...overrides,
    };
  },

  createCompleted(overrides: Partial<Order> = {}): Order {
    return this.create({ status: 'COMPLETED', completedAt: new Date(), ...overrides });
  },
};
```
