# Manual de Usuario — DomiPedidosX 🍔🛵

Sistema web de gestión de pedidos y domicilios para restaurantes.
Proyecto académico — Desarrollo de Software I (2026‑II), Universidad del Valle.

## Índice

1. [Introducción](#1-introducción)
2. [Roles del sistema](#2-roles-del-sistema)
3. [Primeros pasos](#3-primeros-pasos)
4. [Manual del Cliente](#4-manual-del-cliente)
5. [Manual del Operador de Sede](#5-manual-del-operador-de-sede)
6. [Manual de Cocina](#6-manual-de-cocina)
7. [Manual del Administrador](#7-manual-del-administrador)
8. [Preguntas frecuentes y mensajes del sistema](#8-preguntas-frecuentes-y-mensajes-del-sistema)
9. [Glosario de estados de un pedido](#9-glosario-de-estados-de-un-pedido)

---

## 1. Introducción

**DomiPedidosX** permite a un restaurante con una o varias **sedes** publicar su menú,
recibir pedidos a domicilio o para recoger en mostrador, y hacerles seguimiento desde
que se reciben hasta que se entregan.

El sistema distingue cinco tipos de usuario (roles), cada uno con una pantalla y
unos permisos distintos: **Cliente**, **Operador de Sede**, **Cocina**, **Repartidor**
y **Administrador**.

> Este manual explica el uso de la aplicación desde el navegador. Para la instalación
> técnica del proyecto, consulta el `README.md` del repositorio.

---

## 2. Roles del sistema

| Rol | ¿Qué hace en la plataforma? | ¿Necesita sede asignada? |
|---|---|---|
| **Cliente** | Se registra, navega el menú, arma su carrito, confirma pedidos, los sigue y puede cancelarlos. | No |
| **Operador de Sede** | Atiende pedidos telefónicos o de mostrador en nombre de un cliente, y supervisa los pedidos del día de su sede. Tiene acceso limitado al panel de administración para gestionar el menú de su sede. | Sí |
| **Cocina** | Ve el tablero de pedidos de su sede y los va avanzando de estado a medida que se preparan. | Sí |
| **Repartidor** | Rol reservado para la entrega de domicilios. | No |
| **Administrador** | Acceso total al panel de administración: sedes, categorías, productos, usuarios y pedidos. | No |

El rol de cada usuario lo asigna el **Administrador** desde el panel de administración
(sección [7](#7-manual-del-administrador)); un cliente no puede cambiarse el rol por su cuenta.

---

## 3. Primeros pasos

### 3.1 Crear una cuenta (rol Cliente)

1. Entra a la página de inicio y haz clic en **Regístrate**.
2. Completa el formulario:
   - Usuario
   - Nombre y apellido
   - Correo electrónico
   - Teléfono de contacto (solo números, 7 a 15 dígitos; puede empezar con `+`)
   - Contraseña y confirmación de contraseña
3. Al enviar el formulario quedas registrado como **Cliente** e inicias sesión
   automáticamente.

> El correo debe ser único: si ya existe una cuenta con ese correo, el sistema te lo
> indicará. Lo mismo ocurre con el teléfono si tiene un formato inválido.

### 3.2 Iniciar sesión

1. Ve a **Iniciar sesión**.
2. Ingresa tu usuario y contraseña.
3. Si los datos son incorrectos, el sistema muestra: *"Usuario o contraseña
   incorrectos. Revisa los datos e inténtalo de nuevo."*
4. Si tu cuenta fue desactivada por un administrador, verás: *"Esta cuenta está
   desactivada."*

### 3.3 Recuperar contraseña

1. En la pantalla de inicio de sesión, haz clic en **¿Olvidaste tu contraseña?**.
2. Escribe el correo electrónico asociado a tu cuenta y envía el formulario.
3. Si la cuenta existe y está activa, se envía un correo con un enlace para crear
   una nueva contraseña (en el entorno de desarrollo, este correo se ve en la
   consola del servidor en lugar de llegar a una bandeja de entrada real).
4. Abre el enlace del correo y define tu nueva contraseña. El sistema valida que
   no sea demasiado simple, ni completamente numérica, ni muy parecida a tus
   datos personales.
5. Una vez confirmada, ya puedes iniciar sesión con la nueva contraseña.

### 3.4 Cerrar sesión

Haz clic en **Cerrar sesión** en el menú superior. Por seguridad, la sesión expira
automáticamente después de 8 horas de inactividad o al cerrar el navegador.

---

## 4. Manual del Cliente

### 4.1 Ver el menú

- El menú (`Menú`) es público: puedes consultarlo sin iniciar sesión.
- Puedes filtrar los productos por **sede** usando el selector de sede en la parte
  superior del menú.
- Solo se muestran los productos que están **disponibles** en al menos una sede
  activa (o en la sede que elegiste con el filtro). Si un producto se agota en una
  sede, deja de aparecer para esa sede, aunque siga disponible en otra.

### 4.2 Perfil y direcciones

Desde **Mi perfil** puedes:

- Actualizar tu nombre, apellido, correo y teléfono.
- Gestionar tus **direcciones de entrega** (`Mis direcciones`):
  - **Nueva dirección**: nombre (ej. "Casa", "Trabajo"), dirección completa e
    indicaciones para el domiciliario (ej. "Apto 301, portería azul").
  - La primera dirección que guardes queda marcada automáticamente como
    **principal**.
  - Puedes marcar cualquier otra dirección como principal; solo puede existir
    una dirección principal a la vez.
  - Puedes editar o eliminar una dirección. Si eliminas la que era principal,
    el sistema marca otra de tus direcciones como principal automáticamente
    (si tienes más de una guardada).

> Necesitas tener al menos **una dirección guardada** antes de poder confirmar un
> pedido a domicilio.

### 4.3 Armar el carrito

1. Desde el menú, elige un producto y haz clic en **Agregar al carrito**, indicando
   la cantidad deseada (entre 1 y 50 unidades por producto).
2. El carrito solo admite productos de **una sede a la vez**. Si agregas un producto
   de una sede distinta a la que ya tenías en el carrito, el sistema te avisa que el
   carrito anterior se vació y empieza uno nuevo con la nueva sede.
3. En **Mi carrito** puedes:
   - Ver cada línea con su cantidad, precio y subtotal.
   - Actualizar la cantidad de un producto.
   - Quitar un producto del carrito.
   - Ver el subtotal, el costo de domicilio y el total.
4. Si alguno de los productos de tu carrito dejó de estar disponible, el sistema
   te lo advierte antes de dejarte continuar.

El contador junto al ícono del carrito, visible en todo el sitio mientras navegas
como cliente, te indica cuántas unidades llevas acumuladas.

### 4.4 Confirmar un pedido

1. Desde el carrito, haz clic en **Confirmar pedido**.
2. Si no tienes ninguna dirección guardada, el sistema te enviará primero a
   crear una.
3. Completa el formulario de confirmación:
   - **Dirección de entrega** (se preselecciona tu dirección principal).
   - **Método de pago** (simulado): efectivo, tarjeta o transferencia.
   - **Observaciones** (opcional, hasta 300 caracteres): por ejemplo,
     "sin cebolla", "tocar el timbre", etc.
4. Al confirmar, el sistema vuelve a validar que todos los productos sigan
   existiendo y disponibles en la sede, y **congela los precios** al momento de
   la compra. Si algo cambió, verás un mensaje explicando qué pasó (por ejemplo,
   que algún producto ya se agotó) y podrás revisar tu carrito.
5. Si todo es correcto, el pedido se crea con estado **Recibido** y el carrito
   se vacía automáticamente.

### 4.5 Seguimiento del pedido

- Tras confirmar, caes en la pantalla del pedido, donde ves un indicador de
  progreso con los pasos: **Recibido → En preparación → Listo → Entregado**.
- Mientras el pedido siga en curso, esta pantalla se actualiza automáticamente
  para reflejar el estado más reciente.
- En **Mis pedidos** puedes consultar el historial completo de tus pedidos,
  con la sede, la fecha y la cantidad de productos de cada uno.

### 4.6 Cancelar un pedido

- Solo puedes cancelar un pedido **mientras esté en estado "Recibido"**.
- Si la cocina ya empezó a prepararlo (o en cualquier estado posterior), el
  sistema no permite la cancelación y te muestra un mensaje según el caso, por
  ejemplo: *"Tu pedido ya está en preparación y no se puede cancelar."*
- Al cancelar, el pedido no se borra: queda marcado como **Cancelado** y
  conservas el registro en tu historial.

---

## 5. Manual del Operador de Sede

> Este rol está pensado para el personal que atiende pedidos telefónicos o de
> mostrador, y que administra el menú de su propia sede. Requiere tener una
> sede asignada por el Administrador.

### 5.1 Elegir la sede de trabajo

Al entrar al **Panel del operador** o al tablero correspondiente, si aún no has
elegido sede, el sistema te mostrará un selector con las sedes activas. Una vez
elegida, el sistema la recuerda durante tu sesión (puedes cambiarla con la opción
**Cambiar sede**).

### 5.2 Tomar un pedido en nombre de un cliente

1. Entra a **Nuevo pedido** (elegir cliente).
2. Busca al cliente por su usuario o su teléfono.
3. Selecciona al cliente de la lista de resultados. Esto limpia cualquier carrito
   que hubiera quedado abierto, para empezar el pedido desde cero.
4. Navega el menú y agrega productos al carrito igual que lo haría un cliente,
   y confirma el pedido siguiendo los mismos pasos de la sección
   [4.4](#44-confirmar-un-pedido).
5. El pedido queda registrado a nombre del cliente seleccionado, pero el sistema
   guarda también qué operador lo creó.

### 5.3 Panel del operador

El **Panel del operador** muestra los pedidos del **día actual** de tu sede,
ordenados del más reciente al más antiguo, con su cliente y estado. Desde aquí
puedes acceder rápidamente a los demás módulos (menú, tablero de cocina, etc.).

### 5.4 Gestión del menú de tu sede (panel de administración)

El operador tiene acceso limitado al panel de administración (`/admin/`),
restringido a su propia sede:

- **Sedes y categorías**: solo puede verlas, no crearlas, editarlas ni borrarlas.
- **Productos**: puede verlos y filtrarlos por categoría, pero no puede
  crear, editar ni eliminar productos, ni ver el detalle de otras sedes.
- **Disponibilidad por sede (Producto por sede)**: aquí sí puede **agregar y
  editar**, marcando qué productos están disponibles o agotados en su propia
  sede (casilla "disponible"). No puede eliminar registros ni ver los de otras
  sedes.

---

## 6. Manual de Cocina

> Este rol requiere tener una sede asignada.

### 6.1 Tablero de cocina

El **tablero de cocina** muestra los pedidos activos de tu sede organizados en
tres columnas:

| Columna | Pedidos que contiene | Acción disponible |
|---|---|---|
| **Recibido** | Pedidos nuevos que aún no se han empezado a preparar | *Empezar a preparar* |
| **En preparación** | Pedidos que la cocina ya está preparando | *Marcar listo* |
| **Listo** | Pedidos listos para entregar o despachar | *Marcar entregado* |

Cada tarjeta muestra el cliente y los productos del pedido, para que la cocina
sepa exactamente qué preparar.

### 6.2 Avanzar un pedido

1. Haz clic en el botón de acción correspondiente a la columna del pedido
   (por ejemplo, **Marcar listo**).
2. El sistema valida que el pedido siga en el mismo estado que viste en el
   tablero; si alguien más ya lo avanzó mientras tanto, verás un aviso para que
   actualices el tablero y evitar saltarte un paso.
3. Si el pedido ya está en un estado final (**Entregado** o **Cancelado**), no se
   puede modificar y el sistema te lo indica.
4. Al confirmarse el cambio, el pedido se mueve a la siguiente columna
   automáticamente.

> Los pedidos **Entregados** o **Cancelados** dejan de aparecer en el tablero.

---

## 7. Manual del Administrador

El Administrador tiene acceso completo al panel de administración de Django
(`/admin/`) y es el único rol con privilegios de superusuario.

### 7.1 Gestión de usuarios

Desde **Usuarios** puedes:

- Dar de alta nuevos usuarios y asignarles un **rol**: Cliente, Operador de Sede,
  Cocina, Repartidor o Administrador.
- Asignar la **sede** correspondiente. Es **obligatoria** para los roles
  Operador de Sede y Cocina; si intentas guardar uno de estos roles sin sede,
  el sistema rechaza el cambio con el mensaje: *"Los roles operador y cocina
  deben tener una sede asignada."*
- **Activar o desactivar** usuarios. Un usuario desactivado no puede iniciar
  sesión.
- Cambiar el rol de un usuario existente (por ejemplo, ascender un cliente a
  operador).

> Dar de alta a un usuario con rol **Administrador** lo convierte automáticamente
> en superusuario, con acceso total al panel. Un usuario con rol **Operador**
> obtiene acceso al panel de administración (con permisos limitados, ver
> sección [5.4](#54-gestión-del-menú-de-tu-sede-panel-de-administración)).

### 7.2 Gestión de sedes

En **Sedes** puedes crear y editar cada punto de atención:

- Nombre y dirección.
- Horario de apertura y cierre (soporta horarios que cruzan la medianoche,
  por ejemplo de 6:00 p. m. a 2:00 a. m.).
- Estado **activa / inactiva**: una sede inactiva no aparece para los clientes
  ni en los selectores de operador y cocina.

### 7.3 Gestión del menú

- **Categorías**: crear, editar y eliminar las categorías del menú.
- **Productos**: crear, editar y eliminar productos, definiendo nombre,
  categoría, descripción, precio, imagen (opcional) y tiempo de preparación
  en minutos (entre 1 y 240).
- **Producto por sede**: asociar cada producto a una o varias sedes y marcar su
  disponibilidad individual. Esto es lo que determina si el cliente lo ve en el
  menú de cada sede. No puede repetirse la misma combinación de producto y
  sede.

### 7.4 Gestión de pedidos

En **Pedidos** el administrador puede consultar todos los pedidos del sistema,
filtrando por estado o por sede, y revisar el detalle de cada uno (líneas de
producto, cantidades y precios congelados al momento de la compra).

---

## 8. Preguntas frecuentes y mensajes del sistema

**¿Por qué no veo un producto que sí aparece en otra sede?**
La disponibilidad se maneja de forma independiente por sede. Un producto puede
estar agotado en una sede y disponible en otra al mismo tiempo.

**Agregué un producto de otra sede y se vació mi carrito, ¿por qué?**
El carrito solo puede contener productos de una única sede. Al cambiar de sede,
el sistema vacía el carrito anterior para evitar mezclar pedidos de sedes
distintas.

**No puedo confirmar mi pedido.**
Revisa que: (1) tengas al menos una dirección guardada, (2) tu carrito no esté
vacío, y (3) todos los productos de tu carrito sigan disponibles en la sede
elegida.

**Quiero cancelar un pedido y no me deja.**
Solo se pueden cancelar pedidos en estado **Recibido**. Una vez que la cocina
empieza a prepararlo, ya no es posible cancelarlo desde la plataforma.

**Inicié sesión como operador/cocina pero no veo nada.**
Primero debes elegir la sede con la que vas a trabajar, usando el selector que
aparece al entrar al panel o al tablero.

---

## 9. Glosario de estados de un pedido

| Estado | Significado |
|---|---|
| **Recibido** | El pedido fue creado y aún no se empieza a preparar. Es el único estado desde el cual el cliente puede cancelarlo. |
| **En preparación** | La cocina ya está preparando el pedido. |
| **Listo** | El pedido está listo para ser entregado o recogido. |
| **Entregado** | Estado final: el pedido fue entregado al cliente. |
| **Cancelado** | Estado final: el pedido fue cancelado por el cliente mientras estaba en "Recibido". |

---

*Manual generado a partir del contexto del proyecto DomiPedidosX (commits hasta
`fd3f457`). Ante cualquier discrepancia con el comportamiento real de la
aplicación, prevalece el código fuente del repositorio.*

## 5. Administrador General
Controla la operación global de la marca.
* **Configuración del Sistema:** Tiene acceso al panel de administración general. Puede crear nuevas sedes, configurar horarios de atención y establecer tiempos estimados por zonas de cobertura.
* **Gestión de Usuarios:** Puede bloquear usuarios o asignar permisos a los empleados (convertir a un usuario normal en Operador o Cocinero).
* **Reportes:** Visualiza métricas de ventas y ocupación de cocina para la toma de decisiones empresariales.
