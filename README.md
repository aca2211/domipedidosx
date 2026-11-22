# DomiPedidosX 
![Logo DomiPedidosX](docs/img/logo.jpeg)

Sistema Web de Gestión de Pedidos y Domicilios para Restaurantes. Proyecto académico para la asignatura de Desarrollo de Software I (2026-II) - Universidad del Valle.

## Integrantes del Equipo

* **Miguel Ángel Martinez Eraso:** Product Owner & UX/UI
* **Alejandro Cardona Arellano:** Scrum Master & DevOps
* **Juan Manuel Muñoz Delgado:** Backend & DB Engineer
* **Juan Camilo Ramos Hoyos:** Backend Feature Developer
* **Andres Muñoz Moreno:** Frontend Feature Developer

## Stack Tecnológico

* **Backend:** Python 3.14, Django
* **Base de Datos:** SQLite (Desarrollo) / PostgreSQL (Producción)
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap

# Manual de Instalación - DomiPedidosX

Este manual describe los pasos necesarios para descargar, configurar y ejecutar el entorno de desarrollo local de DomiPedidosX.

## Pre-requisitos
Asegúrese de tener instalado en su sistema operativo:
* **Python 3.12.3**
* **Git**
* Entorno virtual de Python (`venv`)

## Pasos de Instalación

**1. Clonar el repositorio y acceder a la rama de desarrollo**
```bash
git clone https://github.com/tu-usuario/domipedidosx.git
cd domipedidosx
git checkout develop
```

**2. Crear y activar el entorno virtual**
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Mac/Linux:
source venv/bin/activate
```

**3. Instalar dependencias**
```bash
pip install -r requirements.txt
```

**4. Configurar variables de entorno**
El sistema buscará las configuraciones en el archivo `settings.py`. Para desarrollo local asegúrese de tener `DEBUG = True`. (Opcional: cree un archivo `.env` si abstrajeron las credenciales).

**5. Preparar la Base de Datos (SQLite)**
Ejecute las migraciones para generar las tablas `users`, `menu` y `pedidos`:
```bash
python manage.py migrate
```

**6. Cargar Datos de Demostración (Recomendado)**
El equipo ha preparado un script que inyecta Sedes, Productos, Usuarios (por rol) y Pedidos de prueba. Ejecute:
```bash
python manage.py cargar_demo
```
*Esto generará automáticamente los siguientes usuarios (con la contraseña `demo1234`):*
* `demo_cliente` (Rol Cliente)
* `demo_operador` (Rol Operador)
* `demo_cocina` (Rol Cocina)
* `demo_admin` (Rol Admin)

**7. Levantar el Servidor**
```bash
python manage.py runserver
```
Acceda a la aplicación abriendo un navegador web en `http://localhost:8000`.

## Flujo de Trabajo (Git Flow)

Trabajaremos estrictamente con Pull Requests (PR). Por favor, crea una rama `feature/nombre-de-la-tarea` a partir de `develop` y envía tu PR hacia `develop`.
