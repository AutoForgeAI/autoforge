# API Design & Frontend Patterns Reference

## Implementation Patterns

### MVC / Controller Layer
```typescript
// Controller: Thin, handles HTTP concerns only
@Controller('/users')
export class UserController {
  constructor(private readonly userService: UserService) {}

  @Post()
  async create(@Body() dto: CreateUserDto): Promise<UserResponse> {
    const user = await this.userService.createUser(dto);
    return UserMapper.toResponse(user);
  }
}
```

### Service Layer (Application/Use Cases)
```typescript
// Service: Orchestrates domain logic, no HTTP concerns
@Injectable()
export class UserService {
  constructor(
    private readonly userRepo: UserRepository,
    private readonly eventBus: EventBus,
  ) {}

  async createUser(dto: CreateUserDto): Promise<User> {
    const user = User.create(dto.email, dto.name);
    await this.userRepo.save(user);
    await this.eventBus.publish(new UserCreatedEvent(user.id));
    return user;
  }
}
```

### Repository Pattern
```typescript
// Repository Interface (Domain Layer)
interface UserRepository {
  findById(id: UserId): Promise<User | null>;
  findByEmail(email: Email): Promise<User | null>;
  save(user: User): Promise<void>;
  delete(id: UserId): Promise<void>;
}

// Repository Implementation (Infrastructure Layer)
@Injectable()
export class PostgresUserRepository implements UserRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async findById(id: UserId): Promise<User | null> {
    const data = await this.prisma.user.findUnique({ where: { id: id.value } });
    return data ? UserMapper.toDomain(data) : null;
  }
}
```

### Domain Entity Pattern
```typescript
// Entity with encapsulated business logic
export class User extends Entity<UserId> {
  private constructor(
    id: UserId,
    private _email: Email,
    private _name: UserName,
    private _status: UserStatus,
  ) {
    super(id);
  }

  static create(email: string, name: string): User {
    return new User(
      UserId.generate(),
      Email.create(email),
      UserName.create(name),
      UserStatus.PENDING,
    );
  }

  activate(): void {
    if (this._status !== UserStatus.PENDING) {
      throw new InvalidOperationError('User already activated');
    }
    this._status = UserStatus.ACTIVE;
  }
}
```

### Value Object Pattern
```typescript
// Immutable Value Object with validation
export class Email extends ValueObject<string> {
  private constructor(value: string) {
    super(value);
  }

  static create(email: string): Email {
    if (!this.isValid(email)) {
      throw new InvalidEmailError(email);
    }
    return new Email(email.toLowerCase().trim());
  }

  private static isValid(email: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }
}
```

### Factory Pattern
```typescript
// Factory for complex object creation
export class OrderFactory {
  constructor(
    private readonly pricingService: PricingService,
    private readonly inventoryService: InventoryService,
  ) {}

  async createOrder(customerId: CustomerId, items: OrderItemDto[]): Promise<Order> {
    const availability = await this.inventoryService.checkAvailability(items);
    if (!availability.allAvailable) {
      throw new InsufficientInventoryError(availability.unavailable);
    }

    const pricing = await this.pricingService.calculate(items);
    return Order.create(customerId, items, pricing);
  }
}
```

## REST API Implementation

### Controller Best Practices
```typescript
@Controller('/api/v1/orders')
export class OrderController {
  @Get()
  @UseGuards(AuthGuard)
  async list(
    @Query() query: ListOrdersQuery,
    @CurrentUser() user: AuthUser,
  ): Promise<PaginatedResponse<OrderSummary>> {
    // Validate access, delegate to service
  }

  @Post()
  @HttpCode(HttpStatus.CREATED)
  async create(
    @Body() dto: CreateOrderDto,
    @CurrentUser() user: AuthUser,
  ): Promise<OrderResponse> {
    // Validate, create, return with Location header
  }

  @Patch(':id')
  async update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateOrderDto,
  ): Promise<OrderResponse> {
    // Partial update with proper validation
  }
}
```

## GraphQL Implementation

### Resolver Pattern
```typescript
@Resolver(() => Order)
export class OrderResolver {
  constructor(
    private readonly orderService: OrderService,
    private readonly orderLoader: OrderDataLoader,
  ) {}

  @Query(() => Order)
  async order(@Args('id', { type: () => ID }) id: string): Promise<Order> {
    return this.orderService.findById(id);
  }

  @ResolveField(() => [OrderItem])
  async items(@Parent() order: Order): Promise<OrderItem[]> {
    return this.orderLoader.loadItems(order.id);
  }

  @Mutation(() => Order)
  async createOrder(@Args('input') input: CreateOrderInput): Promise<Order> {
    return this.orderService.create(input);
  }
}
```

### DataLoader for N+1 Prevention
```typescript
@Injectable()
export class OrderDataLoader {
  constructor(private readonly itemRepo: OrderItemRepository) {}

  private readonly itemsLoader = new DataLoader<string, OrderItem[]>(
    async (orderIds) => {
      const items = await this.itemRepo.findByOrderIds(orderIds);
      return orderIds.map(id => items.filter(item => item.orderId === id));
    }
  );

  loadItems(orderId: string): Promise<OrderItem[]> {
    return this.itemsLoader.load(orderId);
  }
}
```

## Error Handling Patterns
```typescript
// Domain Errors (extend base error)
export class DomainError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message);
    this.name = this.constructor.name;
  }
}

export class EntityNotFoundError extends DomainError {
  constructor(entity: string, id: string) {
    super(`${entity} with id ${id} not found`, 'ENTITY_NOT_FOUND');
  }
}

// Global Error Filter
@Catch()
export class GlobalExceptionFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();

    const { status, body } = this.mapException(exception);
    response.status(status).json(body);
  }
}
```

## Frontend State Management

### Redux Toolkit (Complex Global State)
```typescript
// Store Configuration
import { configureStore } from '@reduxjs/toolkit';
import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['auth', 'settings'], // Only persist these slices
  blacklist: ['api'],              // Never persist API cache
};

export const store = configureStore({
  reducer: {
    auth: authReducer,
    orders: ordersReducer,
    settings: settingsReducer,
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
      },
    }).concat(apiSlice.middleware),
  devTools: process.env.NODE_ENV !== 'production',
});

export const persistor = persistStore(store);
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Typed hooks
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

### Redux Slice Pattern
```typescript
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Async thunk for API calls
export const fetchOrders = createAsyncThunk(
  'orders/fetchOrders',
  async (params: FetchOrdersParams, { rejectWithValue }) => {
    try {
      const response = await ordersApi.getOrders(params);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Failed to fetch orders');
    }
  }
);

interface OrdersState {
  items: Order[];
  selectedId: string | null;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
}

const ordersSlice = createSlice({
  name: 'orders',
  initialState,
  reducers: {
    selectOrder: (state, action: PayloadAction<string>) => {
      state.selectedId = action.payload;
    },
    optimisticUpdate: (state, action: PayloadAction<Order>) => {
      const index = state.items.findIndex(o => o.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = action.payload;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOrders.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.items = action.payload.items;
        state.pagination = action.payload.pagination;
      })
      .addCase(fetchOrders.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.payload as string;
      });
  },
});

// Selectors with memoization
export const selectAllOrders = (state: RootState) => state.orders.items;
export const selectOrderById = (id: string) => (state: RootState) =>
  state.orders.items.find(order => order.id === id);
```

### RTK Query for API Caching
```typescript
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const apiSlice = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/v1',
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Order', 'User', 'Product'],
  endpoints: (builder) => ({
    getOrders: builder.query<PaginatedResponse<Order>, GetOrdersParams>({
      query: (params) => ({
        url: '/orders',
        params,
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.items.map(({ id }) => ({ type: 'Order' as const, id })),
              { type: 'Order', id: 'LIST' },
            ]
          : [{ type: 'Order', id: 'LIST' }],
    }),

    // Mutations with optimistic updates
    updateOrder: builder.mutation<Order, { id: string; data: UpdateOrderDto }>({
      query: ({ id, data }) => ({
        url: `/orders/${id}`,
        method: 'PATCH',
        body: data,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Order', id }],
      async onQueryStarted({ id, data }, { dispatch, queryFulfilled }) {
        // Optimistic update
        const patchResult = dispatch(
          apiSlice.util.updateQueryData('getOrderById', id, (draft) => {
            Object.assign(draft, data);
          })
        );
        try {
          await queryFulfilled;
        } catch {
          patchResult.undo(); // Rollback on failure
        }
      },
    }),
  }),
});

export const {
  useGetOrdersQuery,
  useGetOrderByIdQuery,
  useUpdateOrderMutation,
  useCreateOrderMutation,
} = apiSlice;
```

### Zustand (Lightweight Alternative)
```typescript
import { create } from 'zustand';
import { devtools, persist, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface OrdersStore {
  // State
  orders: Order[];
  selectedId: string | null;
  filters: OrderFilters;
  isLoading: boolean;
  error: string | null;

  // Actions
  setOrders: (orders: Order[]) => void;
  addOrder: (order: Order) => void;
  updateOrder: (id: string, updates: Partial<Order>) => void;
  removeOrder: (id: string) => void;
  selectOrder: (id: string | null) => void;
  setFilters: (filters: Partial<OrderFilters>) => void;
  fetchOrders: () => Promise<void>;
}

export const useOrdersStore = create<OrdersStore>()(
  devtools(
    persist(
      subscribeWithSelector(
        immer((set, get) => ({
          // Initial state
          orders: [],
          selectedId: null,
          filters: { status: 'all', sortBy: 'createdAt' },
          isLoading: false,
          error: null,

          // Actions
          setOrders: (orders) =>
            set((state) => {
              state.orders = orders;
            }),

          addOrder: (order) =>
            set((state) => {
              state.orders.unshift(order);
            }),

          updateOrder: (id, updates) =>
            set((state) => {
              const index = state.orders.findIndex((o) => o.id === id);
              if (index !== -1) {
                Object.assign(state.orders[index], updates);
              }
            }),

          fetchOrders: async () => {
            set((state) => {
              state.isLoading = true;
              state.error = null;
            });
            try {
              const orders = await ordersApi.getOrders(get().filters);
              set((state) => {
                state.orders = orders;
                state.isLoading = false;
              });
            } catch (error) {
              set((state) => {
                state.error = error.message;
                state.isLoading = false;
              });
            }
          },
        }))
      ),
      {
        name: 'orders-storage',
        partialize: (state) => ({ filters: state.filters }), // Only persist filters
      }
    ),
    { name: 'OrdersStore' }
  )
);

// Selectors
export const useSelectedOrder = () =>
  useOrdersStore((state) =>
    state.orders.find((o) => o.id === state.selectedId)
  );

export const useFilteredOrders = () =>
  useOrdersStore((state) => {
    let filtered = state.orders;
    if (state.filters.status !== 'all') {
      filtered = filtered.filter((o) => o.status === state.filters.status);
    }
    return filtered;
  });
```

### TanStack Query (React Query)
```typescript
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Query Client Configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,      // 5 minutes
      gcTime: 30 * 60 * 1000,        // 30 minutes
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: true,
    },
  },
});

// Query Keys Factory
export const orderKeys = {
  all: ['orders'] as const,
  lists: () => [...orderKeys.all, 'list'] as const,
  list: (filters: OrderFilters) => [...orderKeys.lists(), filters] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail: (id: string) => [...orderKeys.details(), id] as const,
};

// Custom Query Hooks
export function useOrders(filters: OrderFilters) {
  return useQuery({
    queryKey: orderKeys.list(filters),
    queryFn: () => ordersApi.getOrders(filters),
    placeholderData: (previousData) => previousData,
  });
}

// Mutation with Optimistic Updates
export function useUpdateOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateOrderDto }) =>
      ordersApi.updateOrder(id, data),

    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: orderKeys.detail(id) });
      const previousOrder = queryClient.getQueryData<Order>(orderKeys.detail(id));

      queryClient.setQueryData<Order>(orderKeys.detail(id), (old) =>
        old ? { ...old, ...data } : old
      );

      return { previousOrder };
    },

    onError: (err, { id }, context) => {
      if (context?.previousOrder) {
        queryClient.setQueryData(orderKeys.detail(id), context.previousOrder);
      }
      toast.error('Failed to update order');
    },

    onSettled: (data, error, { id }) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: orderKeys.lists() });
    },
  });
}
```

## Service Worker & PWA

### Workbox Service Worker
```typescript
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';
import { registerRoute, NavigationRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { BackgroundSyncPlugin } from 'workbox-background-sync';

// Precache static assets
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// App shell - Network First for HTML
registerRoute(
  new NavigationRoute(
    new NetworkFirst({
      cacheName: 'pages-cache',
      networkTimeoutSeconds: 3,
    })
  )
);

// API calls - Network First with fallback
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    networkTimeoutSeconds: 10,
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 5 * 60,
      }),
    ],
  })
);

// Static assets - Cache First
registerRoute(
  ({ request }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'font',
  new CacheFirst({
    cacheName: 'static-assets',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 60,
        maxAgeSeconds: 30 * 24 * 60 * 60,
      }),
    ],
  })
);

// Background Sync for failed POST requests
const bgSyncPlugin = new BackgroundSyncPlugin('apiQueue', {
  maxRetentionTime: 24 * 60,
});

registerRoute(
  ({ url, request }) =>
    url.pathname.startsWith('/api/') &&
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method),
  new NetworkFirst({
    cacheName: 'api-mutations',
    plugins: [bgSyncPlugin],
  }),
  'POST'
);
```

## IndexedDB for Offline Data

### Dexie.js Wrapper
```typescript
import Dexie, { Table } from 'dexie';

interface OrderRecord {
  id: string;
  data: Order;
  syncStatus: 'synced' | 'pending' | 'failed';
  lastModified: number;
}

class AppDatabase extends Dexie {
  orders!: Table<OrderRecord, string>;
  syncQueue!: Table<SyncQueueItem, number>;

  constructor() {
    super('AppDatabase');
    this.version(1).stores({
      orders: 'id, syncStatus, lastModified',
      syncQueue: '++id, entity, entityId, timestamp',
    });
  }
}

export const db = new AppDatabase();

// Repository pattern for IndexedDB
export class OfflineOrderRepository {
  async getAll(): Promise<Order[]> {
    const records = await db.orders.toArray();
    return records.map((r) => r.data);
  }

  async save(order: Order, syncStatus: 'synced' | 'pending' = 'synced'): Promise<void> {
    await db.orders.put({
      id: order.id,
      data: order,
      syncStatus,
      lastModified: Date.now(),
    });
  }

  async getPendingSync(): Promise<OrderRecord[]> {
    return db.orders.where('syncStatus').equals('pending').toArray();
  }
}
```

## Form Handling & Validation

### React Hook Form + Zod
```typescript
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const orderSchema = z.object({
  customerId: z.string().uuid('Invalid customer ID'),
  email: z.string().email('Invalid email address'),
  shippingAddress: z.object({
    street: z.string().min(1, 'Street is required'),
    city: z.string().min(1, 'City is required'),
    state: z.string().length(2, 'Use 2-letter state code'),
    zipCode: z.string().regex(/^\d{5}(-\d{4})?$/, 'Invalid ZIP code'),
  }),
  items: z.array(z.object({
    productId: z.string().uuid(),
    quantity: z.number().int().min(1).max(100),
  })).min(1, 'At least one item required'),
  priority: z.enum(['low', 'normal', 'high', 'urgent']),
});

type OrderFormData = z.infer<typeof orderSchema>;

function OrderForm({ onSubmit }: { onSubmit: (data: OrderFormData) => Promise<void> }) {
  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<OrderFormData>({
    resolver: zodResolver(orderSchema),
    mode: 'onBlur',
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'items',
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {/* Form fields */}
    </form>
  );
}
```

## Internationalization (i18n)

### react-i18next Setup
```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';

i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ['en', 'es', 'fr', 'de', 'ja', 'zh'],
    ns: ['common', 'orders', 'auth', 'errors'],
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
      format: (value, format, lng) => {
        if (format === 'currency') {
          return new Intl.NumberFormat(lng, {
            style: 'currency',
            currency: value.currency || 'USD',
          }).format(value.amount);
        }
        return value;
      },
    },
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
  });
```

## Accessibility (a11y)

### WCAG 2.1 AA Compliance
```typescript
// Accessible Modal/Dialog
function Modal({
  isOpen,
  onClose,
  title,
  children,
}: ModalProps) {
  const titleId = useId();
  const descId = useId();

  // Focus trap and restore
  useEffect(() => {
    if (!isOpen) return;
    const previousFocus = document.activeElement as HTMLElement;
    return () => previousFocus?.focus();
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descId}
    >
      <h2 id={titleId}>{title}</h2>
      <div id={descId}>{children}</div>
      <button onClick={onClose} aria-label="Close modal">×</button>
    </div>
  );
}

// Live Region for Announcements
function LiveAnnouncer() {
  const [message, setMessage] = useState('');

  useEffect(() => {
    window.announce = (msg: string) => {
      setMessage('');
      setTimeout(() => setMessage(msg), 100);
    };
  }, []);

  return (
    <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
      {message}
    </div>
  );
}
```

## Error Boundaries

### Error Boundary Component
```typescript
import { Component, ErrorInfo, ReactNode } from 'react';
import * as Sentry from '@sentry/react';

class ErrorBoundary extends Component<Props, State> {
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    Sentry.captureException(error, {
      extra: { componentStack: errorInfo.componentStack },
    });
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <DefaultErrorFallback error={this.state.error!} />;
    }
    return this.props.children;
  }
}
```
