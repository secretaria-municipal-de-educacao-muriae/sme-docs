// Renderer sem Node: só fala com o preload.
(async () => {
  const status = document.getElementById('api-status');
  const url = document.getElementById('api-url');
  const btn = document.getElementById('btn-pdf');

  try {
    const { baseUrl, port } = await window.smedocs.getApi();
    url.textContent = `${baseUrl} (porta ${port})`;
    status.textContent = 'Casca pronta. Aguardando FastAPI da F4.';
  } catch (err) {
    status.textContent = `Falha no handshake: ${err.message}`;
  }

  window.smedocs.onApiReady((info) => {
    url.textContent = info.baseUrl;
    status.textContent = 'API pronta.';
  });

  btn.addEventListener('click', async () => {
    const r = await window.smedocs.printToPdf({});
    if (!r.canceled) status.textContent = `PDF salvo em ${r.path}`;
  });

  // Fluxo de teste com .docx via CLI Python.
  let docxPath = null;
  const btnDocx = document.getElementById('btn-docx');
  const docxLabel = document.getElementById('docx-path');
  const analiseStatus = document.getElementById('analise-status');
  const tabela = document.getElementById('tabela');
  const corpo = document.getElementById('tabela-corpo');
  const gerarBox = document.getElementById('gerar-box');
  const gerarStatus = document.getElementById('gerar-status');
  const gerarLinks = document.getElementById('gerar-links');

  btnDocx.addEventListener('click', async () => {
    analiseStatus.textContent = '';
    analiseStatus.className = '';
    try {
      const pick = await window.smedocs.pickDocx();
      if (pick.canceled) return;
      docxPath = pick.path;
      docxLabel.textContent = docxPath;
      analiseStatus.textContent = 'Analisando… (primeira vez pode levar ~1 min com as fórmulas)';
      const { descriptors } = await window.smedocs.analyzeDocx({ docxPath });
      corpo.innerHTML = '';
      let totalQ = 0;
      let totalKey = 0;
      for (const d of descriptors) {
        totalQ += d.questoes;
        totalKey += d.com_gabarito;
        const tr = document.createElement('tr');
        const pct = d.questoes ? Math.round((100 * d.com_gabarito) / d.questoes) : 0;
        tr.innerHTML = `<td>${d.numero}</td><td>${d.titulo}</td>`
          + `<td>${d.questoes}</td><td>${pct}%</td><td>${d.pendencias || '—'}</td>`;
        corpo.appendChild(tr);
      }
      tabela.hidden = false;
      gerarBox.hidden = false;
      gerarLinks.innerHTML = '';
      gerarStatus.textContent = '';
      analiseStatus.textContent = `${descriptors.length} descritores · ${totalQ} questões · ${totalKey} com gabarito`;
      analiseStatus.className = 'ok';
    } catch (err) {
      analiseStatus.textContent = `Erro: ${err.message}`;
      analiseStatus.className = 'erro';
    }
  });

  document.getElementById('btn-gerar').addEventListener('click', async () => {
    gerarStatus.textContent = '';
    gerarLinks.innerHTML = '';
    const descritor = document.getElementById('inp-desc').value;
    const formato = document.getElementById('sel-formato').value;
    try {
      gerarStatus.textContent = 'Gerando…';
      const { outputs } = await window.smedocs.generate({ docxPath, descritor, formato });
      gerarStatus.textContent = 'Pronto:';
      gerarStatus.className = 'ok';
      for (const out of outputs) {
        const b = document.createElement('button');
        b.className = 'link';
        b.textContent = `Abrir ${out.split(/[\\/]/).pop()}`;
        b.addEventListener('click', () => window.smedocs.openPath({ target: out }));
        gerarLinks.appendChild(b);
        gerarLinks.appendChild(document.createElement('br'));
      }
    } catch (err) {
      gerarStatus.textContent = `Erro: ${err.message}`;
      gerarStatus.className = 'erro';
    }
  });
})();
