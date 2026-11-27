document.addEventListener('DOMContentLoaded', () => {
    const file = document.querySelector('input[type="file"][name="image"]');
    const url = document.querySelector('input[name="image_url"]');
    if (!file || !url) return;

    const currentFile = file.closest('.form-row').querySelector('.file-upload a');
    const clear = document.querySelector('input[name="image-clear"]');
    const preview = document.createElement('img');
    preview.className = 'product-image-preview';
    preview.alt = 'Vista previa de la imagen del producto';
    preview.referrerPolicy = 'no-referrer';
    preview.hidden = true;

    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    const panel = document.createElement('div');
    panel.className = 'domi-image-panel';

    const title = document.createElement('strong');
    title.textContent = 'Vista previa';

    const placeholder = document.createElement('p');
    placeholder.className = 'domi-image-placeholder';
    placeholder.textContent = 'Agrega una imagen para verla aquí.';

    panel.append(title, placeholder, preview, status);
    const fieldset = url.closest('fieldset');
    if (fieldset?.contains(file)) {
        panel.classList.add('domi-image-panel--side');
        fieldset.append(panel);
    } else {
        url.after(panel);
    }

    let localUrl;

    function updatePreview() {
        if (localUrl) {
            URL.revokeObjectURL(localUrl);
            localUrl = undefined;
        }

        let source = '';
        if (file.files.length) {
            localUrl = URL.createObjectURL(file.files[0]);
            source = localUrl;
        } else if (url.value.trim()) {
            const link = url.value.trim();
            if (/^https?:\/\//i.test(link)) source = link;
        } else if (currentFile && !clear?.checked) {
            source = currentFile.href;
        }

        preview.hidden = true;
        placeholder.hidden = Boolean(source);
        status.textContent = '';
        if (source) {
            preview.src = source;
        } else {
            preview.removeAttribute('src');
        }
    }

    preview.addEventListener('load', () => {
        preview.hidden = false;
    });
    preview.addEventListener('error', () => {
        preview.hidden = true;
        status.textContent = 'No se pudo cargar la vista previa de la imagen.';
    });
    file.addEventListener('change', updatePreview);
    let previewTimer;
    url.addEventListener('input', () => {
        window.clearTimeout(previewTimer);
        previewTimer = window.setTimeout(updatePreview, 450);
    });
    url.addEventListener('change', () => {
        window.clearTimeout(previewTimer);
        updatePreview();
    });
    clear?.addEventListener('change', updatePreview);
    updatePreview();
});
