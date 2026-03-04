# Security Patterns Reference

## OWASP Top 10 Prevention

### A01: Broken Access Control
```typescript
// GOOD: Verify ownership before returning data
app.get('/api/orders/:id', authenticate, async (req, res) => {
  const order = await db.orders.findById(req.params.id);
  if (!order) return res.status(404).json({ error: 'Not found' });
  if (order.userId !== req.user.id && !req.user.roles.includes('admin')) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  res.json(order);
});

// RBAC Implementation
const permissions = {
  'order:read': ['customer', 'support', 'admin'],
  'order:write': ['admin'],
  'order:delete': ['admin'],
};

function authorize(permission: string) {
  return (req, res, next) => {
    const allowedRoles = permissions[permission] || [];
    const hasPermission = req.user.roles.some(role => allowedRoles.includes(role));
    if (!hasPermission) return res.status(403).json({ error: 'Insufficient permissions' });
    next();
  };
}
```

### A02: Cryptographic Failures
```typescript
import argon2 from 'argon2';

async function hashPassword(password: string): Promise<string> {
  return argon2.hash(password, {
    type: argon2.argon2id,
    memoryCost: 65536,
    timeCost: 3,
    parallelism: 4,
  });
}
```

### A03: Injection Prevention
```typescript
// GOOD - Parameterized query
const user = await prisma.user.findUnique({ where: { email } });

// GOOD - Raw query with parameters
const users = await prisma.$queryRaw`
  SELECT * FROM users WHERE email = ${email} AND status = ${status}
`;
```

### A07: XSS Prevention
```typescript
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'strict-dynamic'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:", "https:"],
      connectSrc: ["'self'", "https://api.example.com"],
    },
  },
}));
```

## Rate Limiting (Token Bucket)
```typescript
class TokenBucketRateLimiter {
  async consume(key: string, tokens: number = 1): Promise<RateLimitResult> {
    // Lua script for atomic token bucket operations
    const luaScript = `
      local bucket_key = KEYS[1]
      local bucket_size = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local tokens_requested = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      -- ... token bucket logic
    `;
    // Returns { allowed, remaining, resetAt, retryAfter }
  }
}
```

## JWT Token Validation
```typescript
async function validateToken(token: string): Promise<TokenPayload> {
  const publicKey = await getPublicKey();
  const payload = jwt.verify(token, publicKey, {
    algorithms: ['RS256'],
    issuer: 'https://auth.example.com',
    audience: 'https://api.example.com',
    clockTolerance: 30,
  }) as TokenPayload;

  if (await isTokenRevoked(payload.sub, payload.iat)) {
    throw new UnauthorizedError('Token has been revoked');
  }
  return payload;
}
```

## GDPR Compliance

### Consent Management
```typescript
class ConsentManager {
  async recordConsent(userId: string, purposes: string[], granted: boolean): Promise<void> {
    const records = purposes.map(purpose => ({
      userId, purpose, granted,
      grantedAt: new Date(),
      version: await this.getCurrentPolicyVersion(),
    }));
    await db.consents.createMany({ data: records });
  }

  async hasConsent(userId: string, purpose: string): Promise<boolean> {
    const consent = await db.consents.findFirst({
      where: { userId, purpose },
      orderBy: { grantedAt: 'desc' },
    });
    return consent?.granted === true && !consent.withdrawnAt;
  }
}
```

### Data Export (Right to Access)
```typescript
async function generateExport(userId: string): Promise<Record<string, unknown>> {
  return {
    profile: await db.users.findUnique({ where: { id: userId } }),
    orders: await db.orders.findMany({ where: { userId } }),
    preferences: await db.preferences.findMany({ where: { userId } }),
    consents: await db.consents.findMany({ where: { userId } }),
  };
}
```

### Data Deletion (Right to Erasure)
```typescript
const deletionSteps = [
  { table: 'activityLogs', query: { userId } },
  { table: 'sessions', query: { userId } },
  { table: 'preferences', query: { userId } },
  { table: 'orders', action: 'anonymize', query: { userId } },
  { table: 'users', query: { id: userId } },
];
```
