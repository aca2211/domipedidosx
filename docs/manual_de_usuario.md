# Manual de Usuario - DomiPedidosX

Bienvenido a DomiPedidosX. Este manual explica cómo los diferentes actores (roles) interactúan con la plataforma.

---

## 1. Cliente
Es el usuario final que realiza compras a través de la plataforma.
* **Registro e Inicio de sesión:** Acceda a la página principal. Puede crear una cuenta nueva con su número de teléfono o iniciar sesión si ya está registrado.
* **Hacer un pedido:** Navegue por el menú utilizando los filtros de categorías. Seleccione un producto, personalice los ingredientes o adiciones, y haga clic en "Agregar al carrito".
* **Confirmar:** Vaya a su carrito de compras, verifique el subtotal, ingrese su dirección de entrega (el sistema validará si está en zona de cobertura) y seleccione el método de pago.
* **Seguimiento:** Tras confirmar, se mostrará una pantalla con un semáforo de estados (Recibido, En preparación, En camino, Entregado) para seguir su pedido en tiempo real.

---

## 2. Operador de Sede
Encargado de la gestión local del restaurante.
* **Panel de Pedidos:** Al iniciar sesión, verá un dashboard con los pedidos del día de su sede.
* **Gestión de Menú:** Diríjase a la sección "Menú". Aquí puede crear nuevas categorías y productos. Utilice el interruptor de "Disponibilidad" para apagar un producto si se agotan los ingredientes en su local; esto lo ocultará inmediatamente a los clientes.
* **Asignación Logística:** En el panel de pedidos, cuando un pedido cambie a estado "Listo", podrá seleccionar un repartidor disponible y asignarle la entrega.

---

## 3. Cocina (Staff de Preparación)
El equipo encargado de cocinar, requiere de eficiencia y poco contacto con pantallas complejas.
* **Tablero Kanban:** Su vista principal es un tablero de columnas (Recibido, En Preparación, Listo).
* **Gestión de comandas:** Al llegar un pedido, aparecerá en "Recibido". El cocinero debe hacer clic en "Iniciar preparación" para moverlo de columna (notificando al cliente). Una vez terminado, presiona "Marcar como listo".

---

## 4. Repartidor
Encargado de la entrega final.
* **Panel Móvil:** Al iniciar sesión en su celular, verá una lista de entregas que le han sido asignadas por el operador.
* **Rutas y Cierre:** Puede ver la dirección de entrega de cada pedido y el monto a cobrar (si es efectivo). Una vez entregue el pedido al cliente, debe presionar el botón "Marcar como entregado" para cerrar el ciclo.

---

## 5. Administrador General
Controla la operación global de la marca.
* **Configuración del Sistema:** Tiene acceso al panel de administración general. Puede crear nuevas sedes, configurar horarios de atención y establecer tiempos estimados por zonas de cobertura.
* **Gestión de Usuarios:** Puede bloquear usuarios o asignar permisos a los empleados (convertir a un usuario normal en Operador o Cocinero).
* **Reportes:** Visualiza métricas de ventas y ocupación de cocina para la toma de decisiones empresariales.