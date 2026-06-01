/* ── Index page ── */
if (document.getElementById('carForm')) {
  const dropZone = document.getElementById('dropZone');
  const imageInput = document.getElementById('imageInput');
  const previewGrid = document.getElementById('previewGrid');
  const dropPrompt = document.getElementById('dropPrompt');
  const photoCount = document.getElementById('photoCount');
  const clearBtn = document.getElementById('clearBtn');
  const submitBtn = document.getElementById('submitBtn');
  const form = document.getElementById('carForm');

  let selectedFiles = [];

  dropZone.addEventListener('click', (e) => {
    if (!e.target.classList.contains('remove-photo')) imageInput.click();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  ['dragleave', 'dragend'].forEach(ev =>
    dropZone.addEventListener(ev, () => dropZone.classList.remove('drag-over'))
  );

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles([...e.dataTransfer.files].filter(f => f.type.startsWith('image/')));
  });

  imageInput.addEventListener('change', () => {
    addFiles([...imageInput.files]);
    imageInput.value = '';
  });

  clearBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    selectedFiles = [];
    renderPreviews();
  });

  function addFiles(files) {
    const slots = Math.max(0, 10 - selectedFiles.length);
    selectedFiles = [...selectedFiles, ...files.slice(0, slots)];
    renderPreviews();
  }

  function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    renderPreviews();
  }

  function renderPreviews() {
    if (selectedFiles.length === 0) {
      previewGrid.classList.add('d-none');
      dropPrompt.style.display = '';
      photoCount.textContent = 'No photos selected';
      clearBtn.classList.add('d-none');
      syncInput();
      return;
    }

    dropPrompt.style.display = 'none';
    previewGrid.classList.remove('d-none');
    clearBtn.classList.remove('d-none');
    photoCount.textContent = `${selectedFiles.length} photo${selectedFiles.length !== 1 ? 's' : ''} selected`;

    previewGrid.innerHTML = '';
    selectedFiles.forEach((file, i) => {
      const div = document.createElement('div');
      div.className = 'preview-item';

      const img = document.createElement('img');
      const url = URL.createObjectURL(file);
      img.src = url;
      img.alt = file.name;
      img.onload = () => URL.revokeObjectURL(url);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'remove-photo';
      btn.title = 'Remove';
      btn.textContent = '×';
      btn.addEventListener('click', (e) => { e.stopPropagation(); removeFile(i); });

      div.append(img, btn);
      previewGrid.appendChild(div);
    });

    syncInput();
  }

  function syncInput() {
    const dt = new DataTransfer();
    selectedFiles.forEach(f => dt.items.add(f));
    imageInput.files = dt.files;
  }

  const processingModal = new bootstrap.Modal(document.getElementById('processingModal'));

  form.addEventListener('submit', (e) => {
    if (!form.checkValidity()) {
      e.preventDefault();
      e.stopPropagation();
      form.classList.add('was-validated');
      return;
    }
    processingModal.show();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating…';
  });
}


/* ── Result page ── */
if (typeof RAW_LISTING !== 'undefined') {
  // Render markdown listing
  const listingEl = document.getElementById('listingText');
  if (listingEl && typeof marked !== 'undefined') {
    listingEl.innerHTML = marked.parse(RAW_LISTING);
  } else if (listingEl) {
    listingEl.textContent = RAW_LISTING;
  }

  // Copy button
  const copyBtn = document.getElementById('copyBtn');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(RAW_LISTING);
        copyBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied!';
        copyBtn.classList.replace('btn-outline-primary', 'btn-success');
        setTimeout(() => {
          copyBtn.innerHTML = '<i class="bi bi-clipboard me-1"></i>Copy';
          copyBtn.classList.replace('btn-success', 'btn-outline-primary');
        }, 2500);
      } catch {
        copyBtn.textContent = 'Copy failed';
      }
    });
  }

  // Lightbox
  let currentIdx = 0;
  const lightboxModal = document.getElementById('lightboxModal')
    ? new bootstrap.Modal(document.getElementById('lightboxModal'))
    : null;

  window.openLightbox = function(index) {
    if (!lightboxModal) return;
    currentIdx = index;
    updateLightbox();
    lightboxModal.show();
  };

  function updateLightbox() {
    const img = document.getElementById('lightboxImg');
    const dl = document.getElementById('lightboxDownload');
    const caption = document.getElementById('lightboxCaption');
    if (!img) return;
    img.src = `/image/${RESULT_ID}/${currentIdx}`;
    dl.href = `/download/${RESULT_ID}/${currentIdx}`;
    dl.download = `enhanced-photo-${currentIdx + 1}.jpg`;
    if (caption) caption.textContent = `Photo ${currentIdx + 1} of ${IMAGE_COUNT}`;
    document.getElementById('lightboxPrev').disabled = currentIdx === 0;
    document.getElementById('lightboxNext').disabled = currentIdx === IMAGE_COUNT - 1;
  }

  const prevBtn = document.getElementById('lightboxPrev');
  const nextBtn = document.getElementById('lightboxNext');
  if (prevBtn) prevBtn.addEventListener('click', () => { if (currentIdx > 0) { currentIdx--; updateLightbox(); } });
  if (nextBtn) nextBtn.addEventListener('click', () => { if (currentIdx < IMAGE_COUNT - 1) { currentIdx++; updateLightbox(); } });

  // Click photo grid items to open lightbox
  document.querySelectorAll('.photo-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('a, button')) return;
      openLightbox(parseInt(item.dataset.index));
    });
  });
}
