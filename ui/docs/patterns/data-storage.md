# Data Storage & Analytics Patterns Reference

## Database Design

### SQL Schema Design (PostgreSQL)
```sql
-- Domain-driven schema with proper normalization
CREATE SCHEMA orders;

-- Use UUIDs for distributed systems
CREATE TABLE orders.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers.customers(id),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED')),
    total_amount DECIMAL(12, 2) NOT NULL CHECK (total_amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    shipping_address JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1  -- Optimistic locking
);

-- Composite indexes for common queries
CREATE INDEX idx_orders_customer_status ON orders.orders(customer_id, status);
CREATE INDEX idx_orders_created_at ON orders.orders(created_at DESC);
CREATE INDEX idx_orders_status_created ON orders.orders(status, created_at DESC)
    WHERE status NOT IN ('DELIVERED', 'CANCELLED');

-- Partial index for active orders
CREATE INDEX idx_orders_active ON orders.orders(customer_id, created_at DESC)
    WHERE status IN ('PENDING', 'CONFIRMED', 'SHIPPED');

-- GIN index for JSONB queries
CREATE INDEX idx_orders_metadata ON orders.orders USING GIN (metadata);

-- Table partitioning for large tables
CREATE TABLE orders.order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL,
    product_id UUID NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create partitions by month
CREATE TABLE orders.order_items_2024_01 PARTITION OF orders.order_items
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### NoSQL Schema Design (MongoDB)
```typescript
// Embedded vs Referenced: Embed when data is queried together
interface OrderDocument {
  _id: ObjectId;
  customerId: ObjectId;
  status: OrderStatus;
  items: OrderItem[];  // Embedded - always fetched with order
  shipping: {          // Embedded - 1:1 relationship
    address: Address;
    method: string;
    trackingNumber?: string;
  };
  totals: {
    subtotal: Decimal128;
    tax: Decimal128;
    shipping: Decimal128;
    total: Decimal128;
  };
  // Denormalized for query performance
  customerEmail: string;
  customerName: string;
  createdAt: Date;
  updatedAt: Date;
}

// Index design for query patterns
db.orders.createIndex({ customerId: 1, createdAt: -1 });
db.orders.createIndex({ status: 1, createdAt: -1 });
db.orders.createIndex({ "shipping.trackingNumber": 1 }, { sparse: true });
```

### DynamoDB Single-Table Design
```typescript
interface DynamoDBItem {
  PK: string;  // Partition key
  SK: string;  // Sort key
  GSI1PK?: string;  // Global Secondary Index
  GSI1SK?: string;
  type: string;
  data: Record<string, unknown>;
  ttl?: number;
}

// Access patterns mapped to keys
const accessPatterns = {
  // Get order by ID
  getOrder: { PK: 'ORDER#123', SK: 'ORDER#123' },

  // Get all items for order
  getOrderItems: { PK: 'ORDER#123', SK: 'ITEM#' },  // begins_with

  // Get orders by customer
  getCustomerOrders: { GSI1PK: 'CUSTOMER#456', GSI1SK: 'ORDER#' },

  // Get orders by status (GSI2)
  getOrdersByStatus: { GSI2PK: 'STATUS#PENDING', GSI2SK: '2024-01-15' },
};
```

## Caching Strategies

### Redis Caching Patterns
```typescript
import Redis from 'ioredis';

const redis = new Redis({ host: 'redis', port: 6379 });

// Cache-Aside Pattern
async function getOrder(orderId: string): Promise<Order> {
  const cacheKey = `order:${orderId}`;

  // Try cache first
  const cached = await redis.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // Cache miss - fetch from database
  const order = await db.orders.findById(orderId);

  // Cache with TTL
  await redis.setex(cacheKey, 3600, JSON.stringify(order));

  return order;
}

// Write-Through Pattern
async function updateOrder(orderId: string, updates: Partial<Order>): Promise<Order> {
  const order = await db.orders.update(orderId, updates);

  // Update cache immediately
  await redis.setex(`order:${orderId}`, 3600, JSON.stringify(order));

  return order;
}

// Cache Invalidation with Pub/Sub
async function invalidateOrderCache(orderId: string): Promise<void> {
  await redis.del(`order:${orderId}`);
  await redis.publish('cache-invalidation', JSON.stringify({
    type: 'order',
    id: orderId,
  }));
}

// Distributed Locking
async function withLock<T>(
  key: string,
  ttl: number,
  fn: () => Promise<T>
): Promise<T> {
  const lockKey = `lock:${key}`;
  const lockValue = crypto.randomUUID();

  // Acquire lock with NX (only if not exists)
  const acquired = await redis.set(lockKey, lockValue, 'EX', ttl, 'NX');

  if (!acquired) {
    throw new LockAcquisitionError(`Could not acquire lock: ${key}`);
  }

  try {
    return await fn();
  } finally {
    // Release lock only if we own it (Lua script for atomicity)
    await redis.eval(`
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    `, 1, lockKey, lockValue);
  }
}
```

### Multi-Level Caching
```typescript
// L1: In-memory (fastest, per-instance)
// L2: Redis (fast, shared across instances)
// L3: Database (slowest, source of truth)

class MultiLevelCache {
  private l1 = new LRUCache<string, unknown>({ max: 1000, ttl: 60000 });
  private l2: Redis;

  async get<T>(key: string): Promise<T | null> {
    // L1: Check in-memory cache
    const l1Value = this.l1.get(key);
    if (l1Value) return l1Value as T;

    // L2: Check Redis
    const l2Value = await this.l2.get(key);
    if (l2Value) {
      const parsed = JSON.parse(l2Value);
      this.l1.set(key, parsed);  // Populate L1
      return parsed;
    }

    return null;
  }

  async set<T>(key: string, value: T, ttlSeconds: number): Promise<void> {
    const serialized = JSON.stringify(value);
    this.l1.set(key, value);
    await this.l2.setex(key, ttlSeconds, serialized);
  }
}
```

## CQRS Read Models

### Event-Sourced Projections
```typescript
interface DomainEvent {
  eventId: string;
  aggregateId: string;
  aggregateType: string;
  eventType: string;
  payload: unknown;
  metadata: EventMetadata;
  timestamp: Date;
  version: number;
}

class OrderSummaryProjector {
  async project(event: DomainEvent): Promise<void> {
    switch (event.eventType) {
      case 'OrderCreated':
        await this.onOrderCreated(event);
        break;
      case 'OrderItemAdded':
        await this.onOrderItemAdded(event);
        break;
      case 'OrderCompleted':
        await this.onOrderCompleted(event);
        break;
    }
  }

  private async onOrderCreated(event: DomainEvent): Promise<void> {
    const payload = event.payload as OrderCreatedPayload;
    await this.readDb.orderSummaries.upsert({
      orderId: event.aggregateId,
      customerId: payload.customerId,
      customerName: payload.customerName,
      status: 'PENDING',
      itemCount: 0,
      totalAmount: 0,
      createdAt: event.timestamp,
      lastEventVersion: event.version,
    });
  }
}
```

### Materialized Views
```sql
-- PostgreSQL Materialized View for reporting
CREATE MATERIALIZED VIEW analytics.daily_order_stats AS
SELECT
    date_trunc('day', created_at) AS date,
    COUNT(*) AS order_count,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_order_value,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM orders.orders
WHERE status NOT IN ('CANCELLED')
GROUP BY date_trunc('day', created_at)
WITH DATA;

-- Refresh periodically
CREATE UNIQUE INDEX idx_daily_stats_date ON analytics.daily_order_stats(date);
REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.daily_order_stats;
```

## Analytics & Data Pipelines

### Event Streaming with Kafka
```typescript
interface AnalyticsEvent {
  eventName: string;
  userId: string;
  sessionId: string;
  timestamp: number;
  properties: Record<string, unknown>;
  context: {
    page: string;
    userAgent: string;
    ip: string;
    locale: string;
  };
}

async function trackEvent(event: AnalyticsEvent): Promise<void> {
  await kafka.producer.send({
    topic: 'analytics-events',
    messages: [{
      key: event.userId,
      value: JSON.stringify(event),
      headers: {
        'event-type': event.eventName,
        'event-version': '1',
      },
    }],
  });
}
```

### Data Warehouse Schema (Star Schema)
```sql
-- Fact Table
CREATE TABLE analytics.fact_orders (
    order_key BIGSERIAL PRIMARY KEY,
    date_key INTEGER REFERENCES analytics.dim_date(date_key),
    customer_key INTEGER REFERENCES analytics.dim_customer(customer_key),
    product_key INTEGER REFERENCES analytics.dim_product(product_key),
    order_id UUID,
    quantity INTEGER,
    unit_price DECIMAL(10, 2),
    discount_amount DECIMAL(10, 2),
    total_amount DECIMAL(12, 2)
);

-- Dimension Tables
CREATE TABLE analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    day_of_week INTEGER,
    day_name VARCHAR(10),
    month INTEGER,
    month_name VARCHAR(10),
    quarter INTEGER,
    year INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN
);

CREATE TABLE analytics.dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id UUID,
    email VARCHAR(255),
    segment VARCHAR(50),
    acquisition_date DATE,
    lifetime_value DECIMAL(12, 2),
    -- SCD Type 2 fields
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN
);
```

## Database Migrations

### Prisma Migration Framework
```typescript
// prisma/schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  orders    Order[]

  @@index([email])
  @@map("users")
}

model Order {
  id        String      @id @default(uuid())
  userId    String
  user      User        @relation(fields: [userId], references: [id])
  status    OrderStatus @default(PENDING)
  total     Decimal     @db.Decimal(10, 2)
  createdAt DateTime    @default(now())

  @@index([userId])
  @@index([status])
  @@map("orders")
}
```

### Zero-Downtime Migrations
```typescript
// Phase 1: Add new column (nullable)
ALTER TABLE users ADD COLUMN phone VARCHAR(20);

// Phase 2: Backfill data (application code)
async function backfillPhoneNumbers() {
  const batchSize = 1000;
  let lastId = '';

  while (true) {
    const users = await prisma.$queryRaw`
      SELECT id, legacy_phone FROM users
      WHERE phone IS NULL AND id > ${lastId}
      ORDER BY id
      LIMIT ${batchSize}
    `;

    if (users.length === 0) break;

    await prisma.$transaction(
      users.map(u =>
        prisma.user.update({
          where: { id: u.id },
          data: { phone: normalizePhone(u.legacy_phone) },
        })
      )
    );

    lastId = users[users.length - 1].id;
    await new Promise(r => setTimeout(r, 100)); // Throttle
  }
}

// Phase 3: Add NOT NULL constraint (after backfill complete)
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;

// Phase 4: Remove old column (after code no longer uses it)
ALTER TABLE users DROP COLUMN legacy_phone;
```

## Search Implementation

### Elasticsearch Setup & Indexing
```typescript
import { Client } from '@elastic/elasticsearch';

const elastic = new Client({
  node: process.env.ELASTICSEARCH_URL,
  auth: {
    apiKey: process.env.ELASTICSEARCH_API_KEY,
  },
});

const productIndex = {
  settings: {
    number_of_shards: 3,
    number_of_replicas: 1,
    analysis: {
      analyzer: {
        product_analyzer: {
          type: 'custom',
          tokenizer: 'standard',
          filter: ['lowercase', 'asciifolding', 'product_synonyms', 'product_stemmer'],
        },
        autocomplete_analyzer: {
          type: 'custom',
          tokenizer: 'standard',
          filter: ['lowercase', 'asciifolding', 'autocomplete_filter'],
        },
      },
      filter: {
        product_synonyms: {
          type: 'synonym',
          synonyms: [
            'laptop, notebook, portable computer',
            'phone, mobile, smartphone, cell',
          ],
        },
        autocomplete_filter: {
          type: 'edge_ngram',
          min_gram: 2,
          max_gram: 15,
        },
      },
    },
  },
  mappings: {
    properties: {
      id: { type: 'keyword' },
      name: {
        type: 'text',
        analyzer: 'product_analyzer',
        fields: {
          autocomplete: {
            type: 'text',
            analyzer: 'autocomplete_analyzer',
            search_analyzer: 'standard',
          },
          keyword: { type: 'keyword' },
        },
      },
      description: { type: 'text', analyzer: 'product_analyzer' },
      category: { type: 'keyword' },
      brand: { type: 'keyword' },
      price: { type: 'float' },
      rating: { type: 'float' },
      inStock: { type: 'boolean' },
      tags: { type: 'keyword' },
      popularity: { type: 'rank_feature' },
    },
  },
};
```

### Search Service Implementation
```typescript
interface SearchParams {
  query: string;
  filters?: {
    category?: string[];
    brand?: string[];
    priceMin?: number;
    priceMax?: number;
    inStock?: boolean;
  };
  sort?: 'relevance' | 'price_asc' | 'price_desc' | 'rating';
  page?: number;
  pageSize?: number;
}

class ProductSearchService {
  async search(params: SearchParams): Promise<SearchResult<Product>> {
    const { query, filters = {}, sort = 'relevance', page = 1, pageSize = 20 } = params;

    const must: object[] = [];
    const filter: object[] = [];

    // Full-text search
    if (query) {
      must.push({
        multi_match: {
          query,
          fields: ['name^3', 'name.autocomplete^2', 'description', 'brand^2', 'tags'],
          type: 'best_fields',
          fuzziness: 'AUTO',
          prefix_length: 2,
        },
      });
    }

    // Filters
    if (filters.category?.length) {
      filter.push({ terms: { category: filters.category } });
    }
    if (filters.priceMin !== undefined || filters.priceMax !== undefined) {
      filter.push({
        range: {
          price: {
            ...(filters.priceMin !== undefined && { gte: filters.priceMin }),
            ...(filters.priceMax !== undefined && { lte: filters.priceMax }),
          },
        },
      });
    }

    const response = await elastic.search({
      index: 'products',
      body: {
        from: (page - 1) * pageSize,
        size: pageSize,
        query: {
          bool: {
            must: must.length > 0 ? must : [{ match_all: {} }],
            filter,
          },
        },
        aggs: {
          categories: { terms: { field: 'category', size: 20 } },
          brands: { terms: { field: 'brand', size: 50 } },
        },
        highlight: {
          fields: {
            name: { number_of_fragments: 0 },
            description: { number_of_fragments: 2, fragment_size: 150 },
          },
        },
      },
    });

    return this.formatResponse(response, page, pageSize);
  }
}
```

### Algolia Integration
```typescript
import algoliasearch from 'algoliasearch';

const algolia = algoliasearch(
  process.env.ALGOLIA_APP_ID!,
  process.env.ALGOLIA_API_KEY!
);

const productIndex = algolia.initIndex('products');

await productIndex.setSettings({
  searchableAttributes: ['name', 'brand', 'description', 'tags'],
  attributesForFaceting: [
    'filterOnly(inStock)',
    'searchable(category)',
    'searchable(brand)',
    'price',
  ],
  customRanking: ['desc(popularity)', 'desc(rating)'],
  typoTolerance: true,
  highlightPreTag: '<mark>',
  highlightPostTag: '</mark>',
});
```

## Data Synchronization

### Change Data Capture (CDC)
```typescript
interface CDCEvent<T> {
  before: T | null;
  after: T | null;
  op: 'c' | 'u' | 'd' | 'r';
  ts_ms: number;
}

class CDCProcessor<T> {
  async process(event: CDCEvent<T>, handlers: {
    onCreate?: (data: T) => Promise<void>;
    onUpdate?: (before: T, after: T) => Promise<void>;
    onDelete?: (data: T) => Promise<void>;
  }) {
    if ((event.op === 'c' || event.op === 'r') && handlers.onCreate && event.after)
      await handlers.onCreate(event.after);
    if (event.op === 'u' && handlers.onUpdate && event.before && event.after)
      await handlers.onUpdate(event.before, event.after);
    if (event.op === 'd' && handlers.onDelete && event.before)
      await handlers.onDelete(event.before);
  }
}
```

### CRDTs (Conflict-Free Replicated Data Types)
```typescript
// G-Counter for distributed counting
class GCounter {
  private counts = new Map<string, number>();
  constructor(private nodeId: string) {}

  increment(n = 1) { this.counts.set(this.nodeId, (this.counts.get(this.nodeId) || 0) + n); }
  value() { return [...this.counts.values()].reduce((a, b) => a + b, 0); }
  merge(other: GCounter) {
    const m = new GCounter(this.nodeId);
    for (const [k, v] of this.counts) m.counts.set(k, v);
    for (const [k, v] of other.counts) m.counts.set(k, Math.max(m.counts.get(k) || 0, v));
    return m;
  }
}

// LWW-Register for last-writer-wins semantics
class LWWRegister<T> {
  constructor(public value: T, public ts: number) {}
  set(v: T, ts = Date.now()) { if (ts > this.ts) { this.value = v; this.ts = ts; } }
  merge(o: LWWRegister<T>) { return o.ts > this.ts ? o : this; }
}
```

## Cache Invalidation Strategies

### Tag-Based Invalidation
```typescript
class TaggedCache {
  constructor(private redis: Redis) {}

  async set<T>(key: string, data: T, tags: string[], ttl: number) {
    const pipe = this.redis.pipeline();
    pipe.set(key, JSON.stringify(data), 'EX', ttl);
    tags.forEach(t => { pipe.sadd(t, key); pipe.expire(t, ttl + 3600); });
    await pipe.exec();
  }

  async invalidateTag(tag: string) {
    const keys = await this.redis.smembers(tag);
    if (!keys.length) return 0;
    const pipe = this.redis.pipeline();
    keys.forEach(k => pipe.del(k));
    pipe.del(tag);
    await pipe.exec();
    return keys.length;
  }
}
```

### Stale-While-Revalidate
```typescript
class SWRCache<T> {
  private pending = new Set<string>();

  async get(key: string, fetch: () => Promise<T>, opts: { fresh: number; stale: number }) {
    const cached = await this.redis.get(key);
    if (cached) {
      const { data, exp } = JSON.parse(cached);
      const now = Date.now();
      if (now < exp - opts.stale * 1000) return data;
      if (now < exp) { this.refresh(key, fetch, opts); return data; }
    }
    return this.refresh(key, fetch, opts);
  }

  private async refresh(key: string, fetch: () => Promise<T>, opts: { fresh: number; stale: number }) {
    if (this.pending.has(key)) return;
    this.pending.add(key);
    try {
      const data = await fetch();
      await this.redis.set(key, JSON.stringify({ data, exp: Date.now() + opts.fresh * 1000 }), 'EX', opts.fresh + opts.stale);
      return data;
    } finally { this.pending.delete(key); }
  }
}
```
