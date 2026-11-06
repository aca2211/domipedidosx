# Documentación de la API REST - DomiPedidosX

El proyecto DomiPedidosX expone una API REST para facilitar la integración futura con aplicaciones móviles u otros servicios externos. La documentación interactiva (Swagger/Redoc) está disponible cuando el servidor está en ejecución.

## Accesos Rápidos
* **Swagger UI:** `http://localhost:8000/api/docs/`
* **Esquema JSON:** `http://localhost:8000/api/docs/schema.json`

> **Nota para Postman:** Puedes importar la colección completa de Postman usando el archivo `domipedidosx_collection.json` ubicado en la carpeta `docs/postman/` del repositorio.

## Endpoints Principales

### 1. Autenticación y Usuarios (`/api/users/`)

| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/users/register/` | Registra un nuevo cliente. | No |
| `POST` | `/api/users/login/` | Autentica al usuario y devuelve el token (JWT o Session). | No |
| `GET`  | `/api/users/profile/` | Devuelve los datos del usuario logueado. | Sí |

### 2. Gestión de Menú y Sedes (`/api/menu/`)

| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `GET`  | `/api/menu/sedes/` | Lista todas las sedes activas. | No |
| `GET`  | `/api/menu/products/` | Lista los productos disponibles, con filtros por categoría. | No |
| `POST` | `/api/menu/products/` | Crea un nuevo producto (Solo Operador/Admin). | Sí (Rol Requerido) |

### 3. Pedidos y Flujo (`/api/orders/`)

| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/orders/` | Crea un nuevo pedido desde el carrito. | Sí |
| `GET`  | `/api/orders/{id}/` | Devuelve el detalle y estado actual de un pedido. | Sí |
| `PATCH`| `/api/orders/{id}/status/`| Actualiza el estado del pedido (Cocina/Repartidor). | Sí (Rol Requerido)|