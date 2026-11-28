(() => {
    let seguimiento = document.getElementById('seguimiento-pedido');
    const aviso = document.getElementById('aviso-seguimiento');
    const intervalo = 15000;

    if (!seguimiento || seguimiento.dataset.enCurso !== '1') return;

    async function consultarEstado() {
        try {
            if (document.hidden) return;

            const respuesta = await fetch(seguimiento.dataset.url, {
                cache: 'no-store',
                signal: AbortSignal.timeout(10000),
            });
            if (respuesta.redirected || [401, 403, 404].includes(respuesta.status)) {
                seguimiento.dataset.enCurso = '0';
                aviso.textContent = 'El seguimiento automático ya no está disponible.';
                return;
            }
            if (!respuesta.ok) return;

            const plantilla = document.createElement('template');
            plantilla.innerHTML = await respuesta.text();
            const nuevo = plantilla.content.querySelector('#seguimiento-pedido');

            if (nuevo && nuevo.dataset.estado !== seguimiento.dataset.estado) {
                seguimiento.replaceWith(nuevo);
                seguimiento = nuevo;
                aviso.textContent = `Estado del pedido: ${nuevo.dataset.etiqueta}.`;
            }
        } catch {
            // Un fallo temporal se reintenta en la siguiente consulta.
        } finally {
            if (seguimiento.dataset.enCurso === '1') {
                window.setTimeout(consultarEstado, intervalo);
            }
        }
    }

    window.setTimeout(consultarEstado, intervalo);
})();
