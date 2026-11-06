# Arquitectura del Sistema - DomiPedidosX

Este documento describe la arquitectura de software utilizada para el desarrollo del proyecto DomiPedidosX, basada en el patrón arquitectónico **MTV (Model-Template-View)** provisto por el framework Django.

## Diagrama de Arquitectura

```mermaid
flowchart TD
    %% Definición de Actores
    Cliente(Navegador Web / Cliente Celular)
    Repartidor(Navegador Celular)
    Admin(Panel Web Administrador)
    
    %% Frontera de Internet
    Internet((Internet))
    
    %% Capa de Presentación / Lógica (Django)
    subgraph Django Application [Servidor Django]
        URLs[URL Router / URLs]
        Views[Vistas / Lógica de Negocio]
        Templates[Templates / HTML, CSS, JS, Bootstrap]
        Models[Modelos / ORM]
        API[API REST / Django REST Framework]
    end
    
    %% Capa de Datos
    subgraph Database [Capa de Datos]
        DB[(SQLite Local / PostgreSQL Prod)]
    end

    %% Relaciones
    Cliente --> Internet
    Repartidor --> Internet
    Admin --> Internet
    
    Internet --> URLs
    URLs --> Views
    URLs --> API
    Views --> Models
    Views --> Templates
    API --> Models
    Templates --> Internet
    
    Models <--> DB
```

## Descripción de Componentes

1. **Cliente Web / Móvil:** Los usuarios (Clientes, Operadores, Cocina, Repartidores) interactúan con el sistema a través de cualquier navegador web responsivo (gracias a Bootstrap).
2. **URL Router:** Recibe las peticiones HTTP y las dirige a la vista o endpoint correspondiente.
3. **Vistas (Views) / API:** Contienen la lógica de negocio. Procesan la información, validan permisos de roles y preparan los datos. Se exponen tanto vistas tradicionales (Render) como endpoints REST.
4. **Templates:** Archivos HTML renderizados del lado del servidor que construyen la interfaz visual.
5. **Modelos (ORM):** Abstracción de la base de datos escrita en Python. Traduce las operaciones de las Vistas a consultas SQL seguras.
6. **Base de Datos:** Motor relacional (SQLite para desarrollo, PostgreSQL para producción) que persiste la información de usuarios, pedidos, menús y configuración.