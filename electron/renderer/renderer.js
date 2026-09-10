// Renderer sem Node: só fala com o preload.
(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    docxPath: null,
    descriptors: [],
    formulas: null,
    nextOp: 1,
    analisarArquivo: null,
    importarArquivo: null,
  };

  // Navegação lateral: uma seção visível por vez.
  document.querySelectorAll('.nav').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav').forEach((b) => b.removeAttribute('aria-current'));
      btn.setAttribute('aria-current', 'page');
      document.querySelectorAll('.secao').forEach((s) => s.classList.remove('ativa'));
      $(`secao-${btn.dataset.secao}`).classList.add('ativa');
    });
  });

  function setEstado(el, msg, cls) {
    el.textContent = msg;
    el.className = `estado${cls ? ` ${cls}` : ''}`;
  }

  function detalhesBruta(raw) {
    const d = document.createElement('details');
    d.className = 'bruta';
    const s = document.createElement('summary');
    s.textContent = 'ver detalhes';
    const pre = document.createElement('pre');
    pre.textContent = raw;
    d.append(s, pre);
    return d;
  }

  function botaoAbrir(caminho, rotulo) {
    const b = document.createElement('button');
    b.className = 'link';
    b.type = 'button';
    const nome = String(caminho).split(/[\\/]/).pop();
    b.textContent = rotulo || `Abrir ${nome}`;
    b.addEventListener('click', () => window.smedocs.openPath({ target: caminho }));
    return b;
  }

  function classePct(pct) {
    if (pct === 100) return 'bom';
    if (pct >= 70) return 'medio';
    return 'ruim';
  }

  function irParaGerar(numero) {
    document.querySelector('.nav[data-secao="gerar"]').click();
    $('gerar-tudo').checked = false;
    $('gerar-desc').value = String(numero);
    $('gerar-desc').focus();
  }

  function linhaDescritor(d, pct) {
    const tr = document.createElement('tr');
    tr.dataset.busca = `${d.numero} ${d.titulo}`.toLowerCase();
    const tdN = document.createElement('td');
    const chip = document.createElement('span');
    chip.className = 'desc-num';
    chip.textContent = d.numero;
    tdN.appendChild(chip);
    const tdT = document.createElement('td');
    tdT.className = 'titulo';
    tdT.textContent = d.titulo;
    const tdQ = document.createElement('td');
    tdQ.className = 'num';
    tdQ.textContent = d.questoes;
    const tdG = document.createElement('td');
    const pilula = document.createElement('span');
    pilula.className = `pilula ${classePct(pct)}`;
    pilula.textContent = `${pct}%`;
    pilula.title = `${d.com_gabarito} de ${d.questoes} com gabarito`;
    const barra = document.createElement('div');
    barra.className = `barra ${classePct(pct)}`;
    const fill = document.createElement('span');
    fill.style.width = `${pct}%`;
    barra.appendChild(fill);
    tdG.append(pilula, barra);
    const tdP = document.createElement('td');
    tdP.className = 'num';
    const conta = document.createElement('span');
    if (d.pendencias) {
      conta.className = 'conta-pend alguma';
      conta.textContent = d.pendencias;
      conta.title = `${d.pendencias} questões para revisão`;
    } else {
      conta.className = 'conta-pend zero';
      conta.textContent = '—';
      conta.title = 'sem pendências';
    }
    tdP.appendChild(conta);
    const tdA = document.createElement('td');
    const usar = document.createElement('button');
    usar.className = 'link';
    usar.type = 'button';
    usar.textContent = 'Usar';
    usar.title = `Gerar apostila do descritor ${d.numero}`;
    usar.addEventListener('click', () => irParaGerar(d.numero));
    tdA.appendChild(usar);
    tr.append(tdN, tdT, tdQ, tdG, tdP, tdA);
    return tr;
  }

  function aplicarFiltro() {
    const termo = $('inicio-filtro').value.trim().toLowerCase();
    let visiveis = 0;
    for (const tr of $('inicio-tabela').children) {
      const ok = !termo || tr.dataset.busca.includes(termo);
      tr.hidden = !ok;
      if (ok) visiveis++;
    }
    $('inicio-contagem').textContent =
      `Mostrando ${visiveis} de ${state.descriptors.length} descritores.`;
  }

  // Operação com busy-state por seção e botão cancelar.
  async function operacao({ estadoEl, cancelarBtn, botoes }, rotulo, fn) {
    const opId = state.nextOp++;
    for (const b of botoes) b.disabled = true;
    cancelarBtn.hidden = false;
    cancelarBtn.onclick = () => window.smedocs.cancelOp({ opId });
    setEstado(estadoEl, `${rotulo}…`, 'trabalho');
    try {
      const r = await fn(opId);
      cancelarBtn.hidden = true;
      return r;
    } catch (err) {
      setEstado(estadoEl, `Erro: ${err.message}`, 'erro');
      throw err;
    } finally {
      cancelarBtn.hidden = true;
      for (const b of botoes) b.disabled = false;
    }
  }

  function parseNumeros(texto) {
    return String(texto || '')
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0);
  }

  // ---- Início ----

  function renderInicio(descriptors) {
    state.descriptors = descriptors;
    const corpo = $('inicio-tabela');
    corpo.innerHTML = '';
    let totalQ = 0;
    let totalKey = 0;
    let totalPend = 0;
    for (const d of descriptors) {
      totalQ += d.questoes;
      totalKey += d.com_gabarito;
      totalPend += d.pendencias || 0;
      const pct = d.questoes ? Math.round((100 * d.com_gabarito) / d.questoes) : 0;
      corpo.appendChild(linhaDescritor(d, pct));
    }
    if (!$('inicio-filtro').dataset.ligado) {
      $('inicio-filtro').dataset.ligado = '1';
      $('inicio-filtro').addEventListener('input', aplicarFiltro);
    }
    $('inicio-filtro').value = '';
    aplicarFiltro();
    const pctTotal = totalQ ? Math.round((100 * totalKey) / totalQ) : 0;
    const semGabarito = totalQ - totalKey;
    const resumo = $('inicio-resumo');
    resumo.innerHTML = '';
    const cards = [
      [String(descriptors.length), 'descritores', ''],
      [String(totalQ), 'questões', ''],
      [`${pctTotal}%`, 'com gabarito', pctTotal === 100 ? 'ok' : ''],
      [state.formulas === null ? '…' : String(state.formulas), 'fórmulas inline', ''],
      [String(semGabarito), 'sem gabarito', semGabarito ? 'alerta' : 'ok'],
    ];
    for (const [valor, legenda, cls] of cards) {
      const div = document.createElement('div');
      div.className = `item${cls ? ` ${cls}` : ''}`;
      const strong = document.createElement('strong');
      strong.textContent = valor;
      const span = document.createElement('span');
      span.textContent = legenda;
      div.append(strong, span);
      resumo.appendChild(div);
    }
    const afazeres = $('inicio-afazeres');
    afazeres.innerHTML = '';
    if (!semGabarito && !totalPend) {
      afazeres.textContent = 'Nada pendente.';
      afazeres.className = 'bom';
    } else {
      afazeres.className = '';
      const ul = document.createElement('ul');
      if (semGabarito) {
        const li = document.createElement('li');
        li.textContent = `${semGabarito} sem gabarito — exporte um lote na seção Gabarito.`;
        ul.appendChild(li);
      }
      if (totalPend) {
        const li = document.createElement('li');
        li.textContent = `${totalPend} com pendência — confira na seção Conferir.`;
        ul.appendChild(li);
      }
      afazeres.appendChild(ul);
    }
    $('inicio-painel').hidden = false;
    setEstado(
      $('inicio-estado'),
      `${descriptors.length} descritores · ${totalQ} questões · ${totalKey} com gabarito`,
      'ok',
    );
  }

  async function carregarDocx(docxPath) {
    state.docxPath = docxPath;
    state.formulas = null;
    $('docx-caminho').textContent = docxPath;
    setEstado($('inicio-estado'), 'Analisando… (a primeira vez pode levar cerca de 1 min com as fórmulas)', 'trabalho');
    try {
      const { descriptors } = await window.smedocs.analyzeDocx({ docxPath });
      if (!descriptors.length) {
        setEstado($('inicio-estado'), 'Nenhum descritor reconhecido neste documento. Vá até Conferir para diagnosticar.', 'erro');
        $('inicio-painel').hidden = true;
        return;
      }
      renderInicio(descriptors);
      // Fórmulas vêm do relatório (rápido com cache) e completam o painel.
      try {
        const conf = await window.smedocs.conferirDocx({ docxPath, descritores: [] });
        if (conf.formulas !== null) {
          state.formulas = conf.formulas;
          renderInicio(descriptors);
        }
      } catch {
        // painel segue sem a contagem de fórmulas
      }
    } catch (err) {
      setEstado($('inicio-estado'), `Erro: ${err.message}`, 'erro');
    }
  }

  $('btn-trocar-docx').addEventListener('click', async () => {
    try {
      const pick = await window.smedocs.pickDocx();
      if (!pick.canceled) await carregarDocx(pick.path);
    } catch (err) {
      setEstado($('inicio-estado'), `Erro: ${err.message}`, 'erro');
    }
  });

  // ---- Gerar ----

  $('btn-gerar').addEventListener('click', async () => {
    if (!state.docxPath) {
      setEstado($('gerar-estado'), 'Escolha um .docx no topo antes de gerar.', 'erro');
      return;
    }
    const tudo = $('gerar-tudo').checked;
    const lista = tudo ? [] : parseNumeros($('gerar-desc').value);
    const formatos = Array.from(document.querySelectorAll('.gerar-fmt'))
      .filter((c) => c.checked)
      .map((c) => c.value);
    if (!tudo && !lista.length) {
      setEstado($('gerar-estado'), 'Informe os descritores ou marque "todos".', 'erro');
      return;
    }
    if (!formatos.length) {
      setEstado($('gerar-estado'), 'Marque ao menos um formato (PDF ou DOCX).', 'erro');
      return;
    }
    $('gerar-links').innerHTML = '';
    try {
      const { outputs } = await operacao(
        { estadoEl: $('gerar-estado'), cancelarBtn: $('btn-gerar-cancelar'), botoes: [$('btn-gerar')] },
        'Gerando',
        (opId) => window.smedocs.generate({
          docxPath: state.docxPath,
          descritores: lista,
          tudo,
          formatos,
          semGabarito: $('gerar-sem-gabarito').checked,
          opId,
        }),
      );
      setEstado($('gerar-estado'), 'Pronto:', 'ok');
      const box = $('gerar-links');
      for (const out of outputs) {
        box.appendChild(botaoAbrir(out));
        box.appendChild(document.createElement('br'));
      }
    } catch {
      // estado de erro já exibido por operacao()
    }
  });

  // ---- Conferir ----

  $('btn-conferir').addEventListener('click', async () => {
    if (!state.docxPath) {
      setEstado($('conferir-estado'), 'Escolha um .docx no topo antes de conferir.', 'erro');
      return;
    }
    const lista = parseNumeros($('conferir-desc').value);
    const box = $('conferir-resultado');
    box.innerHTML = '';
    try {
      const { raw, formulas } = await operacao(
        { estadoEl: $('conferir-estado'), cancelarBtn: $('btn-conferir-cancelar'), botoes: [$('btn-conferir')] },
        'Conferindo',
        (opId) => window.smedocs.conferirDocx({ docxPath: state.docxPath, descritores: lista, opId }),
      );
      if (formulas !== null) state.formulas = formulas;
      setEstado($('conferir-estado'), 'Relatório pronto:', 'ok');
      const pre = document.createElement('pre');
      pre.textContent = raw;
      const painel = document.createElement('div');
      painel.appendChild(pre);
      // limita a altura do relatório longo sem perder conteúdo
      pre.style.cssText = 'background:var(--caixa);border:1px solid var(--borda);border-radius:6px;padding:12px;overflow:auto;max-height:320px;white-space:pre-wrap;font-size:13px;';
      box.appendChild(painel);
    } catch {
      // estado de erro já exibido por operacao()
    }
  });

  $('btn-analisar-escolher').addEventListener('click', async () => {
    try {
      const pick = await window.smedocs.pickDocx();
      if (!pick.canceled) {
        state.analisarArquivo = pick.path;
        $('analisar-caminho').textContent = pick.path;
      }
    } catch (err) {
      setEstado($('analisar-estado'), `Erro: ${err.message}`, 'erro');
    }
  });

  $('btn-analisar').addEventListener('click', async () => {
    if (!state.analisarArquivo) {
      setEstado($('analisar-estado'), 'Escolha um arquivo para analisar.', 'erro');
      return;
    }
    const box = $('analisar-resultado');
    box.innerHTML = '';
    try {
      const r = await operacao(
        { estadoEl: $('analisar-estado'), cancelarBtn: $('btn-analisar-cancelar'), botoes: [$('btn-analisar')] },
        'Analisando',
        (opId) => window.smedocs.analisarNovo({
          arquivo: state.analisarArquivo,
          copiar: $('analisar-copiar').checked,
          opId,
        }),
      );
      let totalQ = 0;
      let totalKey = 0;
      for (const d of r.descriptors) {
        totalQ += d.questoes;
        totalKey += d.com_gabarito;
      }
      const linha = document.createElement('p');
      linha.textContent = `${r.descriptors.length} descritores · ${totalQ} questões · ${totalKey} com gabarito`;
      box.appendChild(linha);
      if (r.crossLine) {
        const cross = document.createElement('p');
        cross.textContent = `validação cruzada: ${r.crossLine}`;
        cross.className = r.crossOk ? 'bom' : 'ruim';
        box.appendChild(cross);
      }
      box.appendChild(detalhesBruta(r.raw));
      if ($('analisar-copiar').checked) {
        const copiado = document.createElement('p');
        if (r.copied && r.currentPath) {
          copiado.textContent = 'Adotado em reference/ e definido como documento corrente.';
          copiado.className = 'ok';
          await carregarDocx(r.currentPath);
        } else {
          copiado.textContent = 'A adoção falhou — confira o relatório acima.';
          copiado.className = 'erro';
        }
        box.appendChild(copiado);
      }
      setEstado($('analisar-estado'), 'Análise pronta.', 'ok');
    } catch {
      // estado de erro já exibido por operacao()
    }
  });

  // ---- Gabarito ----

  $('btn-exportar').addEventListener('click', async () => {
    if (!state.docxPath) {
      setEstado($('exportar-estado'), 'Escolha um .docx no topo antes de exportar.', 'erro');
      return;
    }
    const limite = Number($('gabarito-limite').value) || 0;
    const box = $('exportar-links');
    box.innerHTML = '';
    try {
      const r = await operacao(
        { estadoEl: $('exportar-estado'), cancelarBtn: $('btn-exportar-cancelar'), botoes: [$('btn-exportar')] },
        'Exportando lote',
        (opId) => window.smedocs.exportarPendencias({ docxPath: state.docxPath, limite, opId }),
      );
      if (r.empty) {
        setEstado($('exportar-estado'), 'Nenhuma pendência. Todas as questões têm gabarito.', 'ok');
        return;
      }
      setEstado($('exportar-estado'), `${r.quantidade} questões neste lote, de ${r.pendentes} pendentes. Depois: importe o JSON preenchido abaixo.`, 'ok');
      if (r.md) box.appendChild(botaoAbrir(r.md, 'Abrir texto do lote (leia este)'));
      box.appendChild(document.createElement('br'));
      if (r.molde) box.appendChild(botaoAbrir(r.molde, 'Abrir molde de respostas (preencha este)'));
    } catch {
      // estado de erro já exibido por operacao()
    }
  });

  $('btn-importar-escolher').addEventListener('click', async () => {
    try {
      const pick = await window.smedocs.pickJson();
      if (!pick.canceled) {
        state.importarArquivo = pick.path;
        $('importar-caminho').textContent = pick.path;
      }
    } catch (err) {
      setEstado($('importar-estado'), `Erro: ${err.message}`, 'erro');
    }
  });

  $('btn-importar').addEventListener('click', async () => {
    if (!state.importarArquivo) {
      setEstado($('importar-estado'), 'Escolha o JSON preenchido antes de importar.', 'erro');
      return;
    }
    const box = $('importar-resultado');
    box.innerHTML = '';
    try {
      const r = await operacao(
        { estadoEl: $('importar-estado'), cancelarBtn: $('btn-importar-cancelar'), botoes: [$('btn-importar')] },
        'Importando',
        (opId) => window.smedocs.importarGabarito({ arquivo: state.importarArquivo, opId }),
      );
      const p = document.createElement('p');
      p.textContent = `+${r.novas} respostas novas · ${r.antes} antes · ${r.agora} agora · destino: ${r.destino}`;
      p.className = 'ok';
      box.appendChild(p);
      box.appendChild(detalhesBruta(r.raw));
      setEstado($('importar-estado'), 'Importação pronta.', 'ok');
      // painel do acervo pode ter mudado — recarrega em silêncio
      if (state.docxPath) {
        try {
          const { descriptors } = await window.smedocs.analyzeDocx({ docxPath: state.docxPath });
          renderInicio(descriptors);
        } catch {
          // mantém o painel anterior
        }
      }
    } catch {
      // estado de erro já exibido por operacao()
    }
  });

  // ---- Inicialização ----

  (async () => {
    try {
      const { baseUrl, port } = await window.smedocs.getApi();
      $('api-linha').textContent = `ponte CLI pronta · 127.0.0.1:${port} (${baseUrl})`;
    } catch (err) {
      $('api-linha').textContent = `ponte CLI pronta (handshake: ${err.message})`;
    }
    window.smedocs.onApiReady((info) => {
      $('api-linha').textContent = `API pronta: ${info.baseUrl}`;
    });
    $('btn-pdf-teste').addEventListener('click', async () => {
      const r = await window.smedocs.printToPdf({});
      if (!r.canceled) setEstado($('inicio-estado'), `PDF de teste salvo em ${r.path}`, 'ok');
    });
    try {
      const def = await window.smedocs.defaultDocx();
      if (def.path) {
        await carregarDocx(def.path);
      } else {
        setEstado($('inicio-estado'), 'Escolha um .docx no topo para começar.', '');
      }
    } catch (err) {
      setEstado($('inicio-estado'), `Erro: ${err.message}`, 'erro');
    }
  })();
})();
