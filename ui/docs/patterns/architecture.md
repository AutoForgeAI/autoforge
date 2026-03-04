# Architecture Patterns Reference

## Layered Architecture (MVC/Clean)
```
┌─────────────────────────────────┐
│     Presentation / API Layer    │  ← Controllers, GraphQL Resolvers
├─────────────────────────────────┤
│     Application / Use Cases     │  ← Orchestration, no business logic
├─────────────────────────────────┤
│     Domain / Business Logic     │  ← Entities, Value Objects, Services
├─────────────────────────────────┤
│     Infrastructure / Data       │  ← Repositories, External Services
└─────────────────────────────────┘
```

## Multi-Tenancy Architecture

### Isolation Models
```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-TENANCY STRATEGIES                      │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Separate DB    │  Separate Schema │  Shared Schema (Row-Level) │
├─────────────────┼─────────────────┼─────────────────────────────┤
│  Highest        │  Medium          │  Lowest                    │
│  Isolation      │  Isolation       │  Isolation                 │
├─────────────────┼─────────────────┼─────────────────────────────┤
│  Highest Cost   │  Medium Cost     │  Lowest Cost               │
├─────────────────┼─────────────────┼─────────────────────────────┤
│  Enterprise     │  Mid-market      │  SMB / High Volume         │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Tenant Resolution Strategies
```typescript
// 1. Subdomain: acme.app.com
// 2. Header: X-Tenant-ID
// 3. Path: /api/tenants/{id}/...
// 4. JWT claim: token.tenantId

interface TenantResolver {
  resolve(req: Request): Promise<Tenant | null>;
}

// Tenant context middleware
async function tenantMiddleware(req: Request, res: Response, next: NextFunction) {
  const tenant = await tenantResolver.resolve(req);
  if (!tenant) return res.status(404).json({ error: 'Tenant not found' });
  if (!tenant.isActive) return res.status(403).json({ error: 'Tenant suspended' });

  req.tenant = tenant;
  AsyncLocalStorage.run({ tenantId: tenant.id }, () => next());
}
```

### Row-Level Security (PostgreSQL)
```sql
-- Enable RLS
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Create isolation policy
CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Set context per request
SET app.tenant_id = 'tenant-uuid';
```

### Prisma Tenant Extension
```typescript
function createTenantPrisma(tenantId: string) {
  return prisma.$extends({
    query: {
      $allModels: {
        async findMany({ args, query }) {
          args.where = { ...args.where, tenantId };
          return query(args);
        },
        async create({ args, query }) {
          args.data = { ...args.data, tenantId };
          return query(args);
        },
        async update({ args, query }) {
          args.where = { ...args.where, tenantId };
          return query(args);
        },
      },
    },
  });
}
```

### Tenant Configuration
```typescript
interface TenantConfig {
  id: string;
  plan: 'free' | 'pro' | 'enterprise';
  features: {
    maxUsers: number;
    maxStorage: number;
    apiRateLimit: number;
    ssoEnabled: boolean;
    auditLogs: boolean;
  };
}
```
