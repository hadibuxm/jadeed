# Product Management REST APIs

JWT-protected endpoints for creating the product hierarchy. All paths are prefixed with `/product-management/` and expect a `Bearer <access>` header from SimpleJWT.

- **Get JWT tokens** (prerequisite)  
  ```bash
  curl -X POST http://localhost:8000/rest-accounts/api/login/ \
    -H "Content-Type: application/json" \
    -d '{"username":"USER","password":"PASS"}'
  ```
  Use the `access` token from the response in the Authorization header below.

## 1) Create Vision
- **POST** `create-vision/`
- Body:
  ```json
  {
    "name": "Vision title",
    "description": "Optional description"
  }
  ```
- Example:
  ```bash
  curl -X POST http://localhost:8000/product-management/create-vision/ \
    -H "Authorization: Bearer ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"Customer-Centric AI","description":"Streamline support with AI."}'
  ```

## 2) Create Portfolio (child of the organization’s vision)
- **POST** `create-portfolio/`
- Body:
  ```json
  {
    "name": "Portfolio title",
    "description": "Optional description"
  }
  ```
- Example:
  ```bash
  curl -X POST http://localhost:8000/product-management/create-portfolio/ \
    -H "Authorization: Bearer ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"Growth Portfolio","description":"All growth bets"}'
  ```

## 3) Create Product (child of a portfolio)
- **POST** `create-product/`
- Body:
  ```json
  {
    "name": "Product title",
    "description": "Optional description",
    "portfolio_id": 1,
    "github_repository_ids": [10, 11]
  }
  ```
- Notes: `github_repository_ids` must belong to the authenticated user’s GitHub connection. Can be an empty list.
- Example:
  ```bash
  curl -X POST http://localhost:8000/product-management/create-product/ \
    -H "Authorization: Bearer ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name":"Insights Hub",
      "description":"Metrics and dashboards",
      "portfolio_id":1,
      "github_repository_ids":[10,11]
    }'
  ```

## 4) Create Feature (child of a product)
- **POST** `create-feature/`
- Body:
  ```json
  {
    "name": "Feature title",
    "description": "Optional description",
    "product_id": 5,
    "github_repository_id": 10
  }
  ```
- Notes: `github_repository_id` is optional (`null` to skip); repository must belong to the authenticated user.
- Example:
  ```bash
  curl -X POST http://localhost:8000/product-management/create-feature/ \
    -H "Authorization: Bearer ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name":"Alerting",
      "description":"Configurable alerting rules",
      "product_id":5,
      "github_repository_id":10
    }'
  ```
