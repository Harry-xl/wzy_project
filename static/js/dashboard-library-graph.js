/**
 * StarPal 我的资料库 — 统一知识图谱 (ECharts)
 * 所有资料合并为一张力导向图，支持节点下钻
 */
'use strict';

(function () {
  const DS = window.__DS;
  if (!DS) return;

  DS.LibraryGraph = {
    _chart: null,
    _graphData: null,

    async loadGraph() {
      const container = DS.$('#libraryGraphContainer');
      if (!container) return;

      try {
        const resp = await fetch(`http://127.0.0.1:3001/api/library/knowledge-graph?user_id=${DS.userId || 0}`);
        const data = await resp.json();
        if (!data.success || !data.graph) {
          container.innerHTML = '<div class="library-graph-placeholder">暂无知识图谱数据</div>';
          return;
        }

        this._graphData = data.graph;
        const graph = data.graph;

        if (!graph.nodes?.length) {
          container.innerHTML = '<div class="library-graph-placeholder">请先上传资料以生成知识图谱</div>';
          return;
        }

        container.innerHTML = ''; // 清除占位

        if (!this._chart) {
          this._chart = echarts.init(container);
          window.addEventListener('resize', () => this._chart?.resize());
        }

        // 构建力导向图
        const option = {
          tooltip: {
            trigger: 'item',
            formatter: (params) => {
              if (params.dataType === 'node') {
                const d = params.data;
                const cat = graph.categories?.[d.category]?.name || '';
                return `<b>${d.name}</b><br/>覆盖度: ${(d.coverage*100).toFixed(0)}%<br/>状态: ${cat}<br/>资料量: ${d.value||0} 块`;
              }
              return `${params.data.source} → ${params.data.target}<br/>${params.data.label||''}`;
            },
          },
          legend: {
            data: (graph.categories || []).map(c => c.name),
            bottom: 10,
          },
          series: [{
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            force: { repulsion: 300, edgeLength: [100, 300], gravity: 0.1 },
            data: graph.nodes.map(n => ({
              ...n,
              itemStyle: { color: (graph.categories?.[n.category]?.itemStyle?.color || '#9CA3AF') },
            })),
            links: graph.links || [],
            categories: graph.categories || [],
            label: { show: true, fontSize: 11, color: 'var(--color-text)' },
            lineStyle: { color: 'var(--color-border)', curveness: 0.2 },
            emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
          }],
        };

        this._chart.setOption(option, true);

        // 节点点击 → 获取该粗粒度知识点下第一个子知识点，打开学习卡片
        this._chart.off('click');
        this._chart.on('click', async (params) => {
          if (params.dataType === 'node') {
            await this._openCardForNode(params.data.id);
          }
        });

      } catch (_) {
        container.innerHTML = '<div class="library-graph-placeholder">加载失败</div>';
      }
    },

    async _openCardForNode(nodeName) {
      // 获取覆盖度数据，找到该粗粒度知识点下第一个可用的子知识点
      try {
        const cResp = await fetch(`http://127.0.0.1:3001/api/library/knowledge-coverage?user_id=${DS.userId || 0}`);
        const cData = await cResp.json();
        const details = cData.success ? (cData.coverage?.details || []) : [];

        // 找到该粗粒度下的子知识点，优先选已覆盖的
        const subTopics = details.filter(d => d.parent_kp === nodeName);
        const covered = subTopics.filter(d => d.status === 'covered');
        const target = covered.length ? covered[0] : subTopics[0];
        if (!target) {
          Utils.showToast('该知识点下暂无子知识点', 'warning');
          return;
        }

        // 打开学习卡片
        if (DS.LearningCardModal) {
          DS.LearningCardModal.open(target.sub_topic_id);
        }
      } catch (_) {
        Utils.showToast('加载失败', 'error');
      }
    },

    highlightUncovered() {
      if (!this._chart || !this._graphData?.nodes) return;
      const option = this._chart.getOption();
      const nodes = option.series?.[0]?.data || [];
      const updated = nodes.map(n => {
        if (n.coverage === 0 && n.value === 0) {
          return { ...n, itemStyle: { color: '#EF4444', shadowBlur: 20, shadowColor: '#EF444480' } };
        }
        return n;
      });
      this._chart.setOption({ series: [{ data: updated }] });
      setTimeout(() => {
        if (this._chart) this._chart.setOption({ series: [{ data: this._graphData.nodes }] });
      }, 3000);
      Utils.showToast('已高亮未覆盖的核心知识点（红色闪烁）', 'info');
    },
  };
})();
