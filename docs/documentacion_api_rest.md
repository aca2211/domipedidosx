# Documentación de Rutas Web (Endpoints) - DomiPedidosX

Actualmente, DomiPedidosX opera mediante renderizado del lado del servidor (SSR) utilizando el motor de plantillas de Django. Las siguientes son las rutas (URLs) principales mapeadas en el sistema para cada módulo.

## 1. Módulo de Usuarios (`users.urls`)

| Método | Ruta | Descripción | Rol Requerido |
| :--- | :--- | :--- | :--- |
| `GET/POST` | `/login/` | Iniciar sesión en la plataforma. | Público |
| `GET/POST` | `/registro/` | Crear una nueva cuenta de cliente. | Público |
| `GET/POST` | `/perfil/` | Ver o actualizar datos de contacto. | Cliente |
| `GET/POST` | `/direcciones/nueva/` | Registrar una nueva dirección de entrega. | Cliente |
| `POST` | `/recuperar/` | Envía correo de recuperación de contraseña (HU03). | Público |

## 2. Módulo de Menú (`menu.urls`)

| Método | Ruta | Descripción | Rol Requerido |
| :--- | :--- | :--- | :--- |
| `GET` | `/menu/?sede={id}` | Muestra el catálogo de productos filtrado por sede y disponibilidad. | Público |
| `GET/POST` | `/admin/menu/` | Gestión administrativa de categorías, sedes y productos. | Operador / Admin |

## 3. Módulo de Pedidos (`pedidos.urls`)

| Método | Ruta | Descripción | Rol Requerido |
| :--- | :--- | :--- | :--- |
| `GET` | `/carrito/` | Visualizar resumen, subtotal y total del carrito. | Cliente |
| `POST` | `/carrito/agregar/` | Agrega un producto a la sesión del carrito. | Cliente |
| `GET/POST` | `/pedido/confirmar/` | Checkout: Confirmar dirección, pago y crear orden (HU14). | Cliente |
| `GET` | `/mis-pedidos/` | Historial de órdenes generadas por el usuario. | Cliente |
| `GET` | `/cocina/tablero/?sede={id}` | Tablero Kanban de cocina (HU18). | Cocina |
| `POST` | `/cocina/pedido/{id}/avanzar/` | Cambiar el estado de un pedido (HU19). | Cocina |
| `GET` | `/operador/panel/` | Dashboard con pedidos del día en una sede específica (HU21). | Operador |
