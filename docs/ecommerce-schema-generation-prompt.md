# E-Commerce OpenAPI Schema — Generation Prompt

> Use this document as a **prompt to hand to an AI assistant** (ChatGPT, Claude, Copilot, etc.)
> to generate a well-formed **OpenAPI 3.0.x** specification of your e-commerce API, ready to
> upload to the **AiCommerce AI integration service**.
>
> A complete, working reference schema that was uploaded and synced successfully is provided
> in `openapi-1.yaml` (same folder as this document). Use it as the structural template.

---

## Instructions to the AI

You are an API documentation expert. Your task is to generate a complete, valid
**OpenAPI 3.0.3** specification (YAML) for the e-commerce REST API described by the user.

The specification will be uploaded to an **AI commerce integration service** that
automatically:

1. **Reads your OpenAPI spec** to discover the base URL, authentication, endpoints, and
   response schemas.
2. **Logs in** to your API using the login endpoint described in the spec.
3. **Detects canonical entities** — `product`, `category`, `customer`, `order`, `coupon`,
   `inventory` — from your endpoint paths and response fields.
4. **Fetches** each entity's list endpoint (following your pagination).
5. **Maps** your source fields to the platform's unified commerce model (using an LLM guided
   by your spec **and** by real sample responses).
6. **Stores** the normalized data and indexes it for AI recommendations/search.

Generate the spec **only from the information the user provides**. Never invent endpoints,
fields, or credentials that the user did not state. If something is missing, ask for it.

---

## 1. Mandatory structure (OpenAPI 3.0.x)

- `openapi: 3.0.3`
- `info.title`, `info.version`, and a short `info.description` naming the platform.
- **`servers`** — REQUIRED. One entry with the real base URL of your API
  (e.g. `https://mult-vendor-ecommerce.runasp.net`). This is how the service finds your host.
- `components.securitySchemes` — a `BearerAuth` scheme:
  ```yaml
  components:
    securitySchemes:
      BearerAuth:
        type: http
        scheme: bearer
        bearerFormat: JWT
  ```
- All **response bodies** on GET/POST endpoints should reference a named schema in
  `components.schemas` via `$ref` (do not leave a `200` response without a schema). The
  discovery step uses these schemas to understand your payloads.
- Keep schemas simple: prefer `type: object` + `properties` with concrete types
  (`string`, `integer`, `number`, `boolean`, `array`). Avoid deep `allOf`/`anyOf`/`oneOf`
  wrappers and inline nested objects where a flat shape is possible.

---

## 2. Authentication & login (critical)

The service must be able to obtain a token automatically. Provide:

- An **unauthenticated** login endpoint (e.g. `POST /api/Auth/login`) with a body schema that
  includes at least `email` and `password` (`format: email` on the email).
- A login **response schema that includes a `token` field** (and optionally `expiresAt`),
  e.g.:
  ```yaml
  AuthResponse:
    type: object
    properties:
      isSuccess: { type: boolean }
      message:   { type: string }
      token:     { type: string }
      expiresAt: { type: string, format: date-time }
  ```
- **Protect admin-scoped list endpoints with `security: [BearerAuth: []]`** so the service
  can use an admin JWT to read them. Recommended protected admin lists: **all users**,
  **all orders**, **all coupons**.
- The login token is used only for the sync and is **never stored** by the platform.

---

## 3. Endpoint coverage & naming (what the service recognizes)

Use **plural resource names** in your path segments. The classifier maps these names to
canonical entities:

| Canonical entity | Recognized path names (last segment) | Example paths |
|---|---|---|
| `product` | `products`, `items`, `goods`, `merchandise`, `brands`, `variants`, `skus` | `/api/Products` |
| `order` | `orders`, `purchases`, `invoices`, `transactions` | `/api/admin/orders`, `/api/Checkout/my-orders` |
| `customer` | `customers`, `users`, `clients`, `accounts`, `subscribers` | `/api/admin/users` |
| `category` | `categories`, `collections` | `/api/Categories` |
| `coupon` / `discount` | `coupons`, `discounts`, `promotions`, `promo_codes` | `/api/admin/coupons` |
| `inventory` | `inventory`, `stock`, `variants` | `/api/Products/my-inventory` |

A GET on a path **without** an `{id}` parameter is treated as the **list** endpoint for that
entity (e.g. `GET /api/Products` → product list). A GET on a path **with** `{id}` is the
detail endpoint. Include both when both exist.

### Required list endpoints (include all that exist in your API)

| Entity | List endpoint shape | Notes |
|---|---|---|
| `product` | `GET /api/Products` | The single most important endpoint |
| `category` | `GET /api/Categories` | |
| `customer` | `GET /api/admin/users` (protected) | Needed for customer analytics |
| `order` | `GET /api/admin/orders` (protected) **or** `GET /api/Checkout/my-orders` | Prefer the admin list — returns all orders |
| `coupon` | `GET /api/admin/coupons` (protected) | Synced into the generic `entities` store |

Each list endpoint must declare a `200` response schema.

---

## 4. Response envelope & pagination (match your real API)

The service **auto-detects** many shapes, but for best results be explicit and consistent.

### Recommended envelope
Wrap list responses in a stable envelope object with an array under a `data` key:
```yaml
GeneralResponseProductList:
  type: object
  properties:
    isSuccess: { type: boolean }
    message:   { type: string }
    data:
      type: array
      items: { $ref: '#/components/schemas/ProductDto' }
```
The extractor also understands top-level keys named `data`, `results`, `items`, `records`,
`rows`, `response`, `content`, and **bare top-level arrays**.

### Pagination (declare it explicitly)
If your API paginates, describe it so the sync can page through all records:

- **Page number style** (recommended, matches the reference spec) — query params
  `PageNumber` and `PageSize` (both `type: integer`, with defaults `1` and `10`), and include
  a total in the response envelope, e.g.:
  ```yaml
  data:
    type: object
    properties:
      totalCount: { type: integer }
      pageNumber: { type: integer }
      pageSize:   { type: integer }
      data:
        type: array
        items: { $ref: '#/components/schemas/ProductDto' }
  ```
- **Offset/limit style** — query params such as `offset` / `limit`.
- **Cursor style** — a `cursor` query param plus a `nextCursor` (or `nextPageToken`) field in
  the response.
- **Header-link style** — a `Link` response header (RFC 5988) if supported.

Whatever you choose, the **schema must match the real JSON your API returns**. Mismatches
between spec and reality are the #1 cause of failed syncs (see pitfalls).

---

## 5. Field naming guidance per entity

Use the source field names below (or close synonyms). The integration maps your names to the
platform's canonical model, so **clear commerce names in the schema + real responses** give
the best mapping. The `id` field must be unique and stable for each record.

### `product` (recommended fields)
| Canonical | Recommended source names | Notes |
|---|---|---|
| `id` | `id` | integer or string, REQUIRED |
| `name` | `name`, `title` | product title |
| `description` | `description` | |
| `price` | `price` | numeric (decimal) |
| `stockQuantity` | `stockQuantity`, `quantity`, `stock` | integer |
| `imageUrl` | `imageUrl`, `image`, `images` | string or array of strings |
| `categoryId` | `categoryId` | include it — enables direct category link |
| `categoryName` | `categoryName` | include it as a fallback link (see note) |
| `sku` | `sku`, `barcode`, `code` | |
| `vendor` / `brand` | `sellerName`, `brand`, `vendor` | |
| `productType` / `type` | `productType`, `type`, `categoryName` | |
| `status` | `status` | `active`/`inactive`/`draft` |
| `weight` | `weight` | |
| `handle` / `slug` | `handle`, `slug` | optional |
| `tags` | `tags`, `labels` | array of strings |

> **categoryName tip:** the reference API omits `categoryId` on its product *list* response.
> The platform falls back to matching `categoryName` against the synced categories, so
> including **both** `categoryId` and `categoryName` gives the most reliable category linking.

### `category`
`id` (required), `name` (required), `description`, `imageUrl`, `parentId` (for
subcategories), `sortOrder`, `handle`/`slug`.

### `customer` / `user`
`id` (required), `email`, `firstName`, `lastName`, `phoneNumber`, `addresses`, `city`,
`country`, `totalSpent`, `ordersCount`, `tags`, `createdAt`.

> **Important:** `firstName` / `lastName` / `phoneNumber` / `email` must be **plain strings**
> in the real response. Some APIs return them as one-element arrays — the platform now
> coerces arrays to strings, but plain strings are still the cleanest input.

### `order`
`id` (required), `customerId`, `customerEmail`/`email`, `lineItems` (array of
`{productId, name, quantity, price, total}`), `subtotal`, `total`, `tax`, `discount`,
`shippingPrice`, `status`, `financialStatus`, `fulfillmentStatus`, `currency`, `createdAt`,
`shippingAddress`, `billingAddress`.

### `coupon`
`id` (required), `code`, `discountPercentage` (or `discountAmount`), `expiryDate`,
`usageLimit`, `usageCount`, `status`, `minimumOrderAmount`. Coupons are stored in the
platform's generic `entities` store, so arbitrary extra fields are preserved.

---

## 6. Value formatting rules

- **Prices / money:** return as **numbers** (`type: number`) or as a money object
  `{ "amount": 1500.0, "currency": "USD" }`. The platform normalizes both. Never return
  price as a pre-formatted string like `"$1,500.00"`.
- **Currency:** 3-letter ISO code (`USD`, `EGP`, `EUR`).
- **IDs:** integers or UUID strings, unique per record, stable across calls.
- **Dates:** ISO-8601 strings (`format: date-time`).
- **Booleans:** real booleans (`true`/`false`), not `"yes"`/`"no"` strings.

---

## 7. Pitfalls to avoid (lessons from production syncs)

1. **Spec must match the real response, byte-for-byte.** Field names, casing, and types in
   `components.schemas` must equal the JSON your API actually returns on each endpoint. If
   the schema says `firstName: string` but the API returns `["mouren mohsen"]`, the sync
   fails validation on that record.
2. **Never leave a `200` list response without a response schema.** The discovery and LLM
   mapping rely on it.
3. **Do not return string fields as arrays** (`firstName`, `email`, `phone`, `status`,
   `name`). Use plain strings.
4. **Keep list endpoints GET-only and idempotent.** The sync reads with GET; it never
   writes to your system.
5. **Don't hide the login endpoint behind auth.** The service needs it to obtain the JWT.
6. **Use explicit plural path names**, not acronyms or opaque routes (`/api/v2/catalog/get`
   is worse than `/api/Products`).
7. **Don't overload one endpoint with several unrelated entity shapes.** Prefer one list
   endpoint per entity.
8. **Include the `servers` block.** Without a base URL the sync cannot run.
9. **Guard against unauthenticated admin lists being 401/403 for a normal login.** If a
   customer login can't read `/api/admin/users`, the customer/order/coupon entities are
   skipped gracefully — provide an admin-capable credential when activating the connection.

---

## 8. Reference template

Use this skeleton (it mirrors the working `openapi-1.yaml`). Replace the placeholder values
with the real API details:

```yaml
openapi: 3.0.3
info:
  title: <Your E-Commerce API>
  description: OpenAPI spec for <Platform name> — enables auto-discovery, canonical
    integration, and AI recommendations.
  version: 1.0.0

servers:
  - url: <https://your-api.example.com>

paths:
  /api/Auth/login:
    post:
      tags: [Authentication]
      summary: Login and obtain JWT
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LoginDto' }
      responses:
        '200':
          description: Login success
          content:
            application/json:
              schema: { $ref: '#/components/schemas/AuthResponse' }

  /api/Products:
    get:
      tags: [Products]
      summary: List products
      parameters:
        - { name: PageNumber, in: query, required: false, schema: { type: integer, default: 1 } }
        - { name: PageSize,   in: query, required: false, schema: { type: integer, default: 10 } }
      responses:
        '200':
          description: Product list
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ProductListResponse' }

  /api/admin/users:
    get:
      tags: [Admin Management]
      summary: List all users
      security: [BearerAuth: []]
      responses:
        '200':
          description: User list
          content:
            application/json:
              schema: { $ref: '#/components/schemas/UserListResponse' }

  /api/admin/orders:
    get:
      tags: [Admin Management]
      summary: List all orders
      security: [BearerAuth: []]
      responses:
        '200':
          description: Order list
          content:
            application/json:
              schema: { $ref: '#/components/schemas/OrderListResponse' }

  /api/admin/coupons:
    get:
      tags: [Admin Management]
      summary: List all coupons
      security: [BearerAuth: []]
      responses:
        '200':
          description: Coupon list
          content:
            application/json:
              schema: { $ref: '#/components/schemas/CouponListResponse' }

  /api/Categories:
    get:
      tags: [Categories]
      summary: List categories
      responses:
        '200':
          description: Category list
          content:
            application/json:
              schema: { $ref: '#/components/schemas/CategoryListResponse' }

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    LoginDto:
      type: object
      required: [email, password]
      properties:
        email:    { type: string, format: email }
        password: { type: string }

    AuthResponse:
      type: object
      properties:
        isSuccess: { type: boolean }
        token:     { type: string }
        expiresAt: { type: string, format: date-time }

    ProductDto:
      type: object
      properties:
        id:            { type: integer }
        name:          { type: string }
        description:   { type: string }
        price:         { type: number, format: decimal }
        stockQuantity: { type: integer }
        imageUrl:      { type: string }
        categoryId:    { type: integer }
        categoryName:  { type: string }
        sku:           { type: string }
        status:        { type: string }

    ProductListResponse:
      type: object
      properties:
        isSuccess: { type: boolean }
        message:   { type: string }
        data:
          type: object
          properties:
            totalCount: { type: integer }
            pageNumber: { type: integer }
            pageSize:   { type: integer }
            data:
              type: array
              items: { $ref: '#/components/schemas/ProductDto' }

    # ... CategoryDto, UserDto, OrderDto, CouponDto + their ListResponse envelopes
    #     following the same pattern
```

---

## 9. Final checklist (before uploading)

- [ ] Valid OpenAPI **3.0.x** (validate with `npx @apidevtools/swagger-cli validate`)
- [ ] `servers[0].url` is the real, reachable base URL
- [ ] `POST .../login` (unauthenticated) returns a `token`
- [ ] `GET /api/Products` (list) has a `200` schema whose `data` is an array
- [ ] Admin lists (`users`, `orders`, `coupons`) are protected with `BearerAuth`
- [ ] Schema field names/types match the **actual JSON responses**
- [ ] `id` fields are present on every list item
- [ ] Prices are numbers or `{amount, currency}` objects
- [ ] No string fields are declared as arrays
- [ ] Pagination query params (`PageNumber`/`PageSize` or `offset`/`limit`/`cursor`) are declared
- [ ] Tested: upload → connection shows detected entities → run a sync → records land in
      products/categories/customers/orders (+ entities for coupons)

---

## 10. What happens after upload (so the schema makes sense)

1. **Upload** the `.yaml`/`.json` file; the service parses and fingerprints it.
2. **Connect** → the platform detects entities, endpoints, and suggests field mappings
   (rule-based + LLM-assisted).
3. **Sync** → for each entity: login → fetch list pages → LLM maps source fields to the
   unified model using your spec + real samples → records are normalized and upserted into
   Mongo (`products`, `categories`, `customers`, `orders`, `entities`) → text is vectorized
   for AI search/recommendations.
4. **Verify** → check per-entity fetched/mapped/upserted counts and sample records.
