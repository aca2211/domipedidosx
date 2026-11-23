# Arquitectura del Sistema - DomiPedidosX

Este documento describe la arquitectura de software utilizada en DomiPedidosX. El sistema está construido de forma monolítica bajo el framework Django, utilizando el patrón **MTV (Model-Template-View)** con renderizado del lado del servidor (SSR).

## Diagrama de Arquitectura

```mermaid
flowchart TD
    %% Actores
    Cliente(Navegador Web / Móvil)
    Operador(Navegador PC/Tablet)
    Cocina(Navegador Tablet/Pantalla)
    Admin(Panel Admin Django)
    
    Internet((Internet))
    
    %% Capa Django
    subgraph Django Application [Servidor Django - MTV]
        URLs[urls.py / Enrutador]
        
        subgraph Apps [Aplicaciones]
            UsersApp[App: users]
            MenuApp[App: menu]
            PedidosApp[App: pedidos]
        end
        
        Views[views.py / Lógica y Sesiones]
        Templates[Templates HTML + Bootstrap]
        Models[models.py / ORM]
    end
    
    %% Capa de Datos
    subgraph Database [Capa de Datos]
        DB[(SQLite / db.sqlite3)]
    end

    %% Relaciones
    Cliente --> Internet
    Operador --> Internet
    Cocina --> Internet
    Admin --> Internet
    
    Internet --> URLs
    URLs --> Apps
    Apps --> Views
    Views --> Models
    Views --> Templates
    Templates --> Internet
    
    Models <--> DB
```

## Componentes Clave
1. **Aplicaciones Modulares:** El proyecto se divide en `users` (autenticación, roles y direcciones), `menu` (sedes, categorías y productos), y `pedidos` (carrito en sesión transitoria y motor transaccional de órdenes).
2. **Sistema de Sesiones:** El carrito de compras no persiste en base de datos de inmediato; utiliza las sesiones seguras de Django (`request.session`) para almacenar temporalmente los ítems hasta el checkout.
3. **Capa de Presentación:** Utiliza el motor de plantillas de Django renderizando vistas HTML con Bootstrap.
