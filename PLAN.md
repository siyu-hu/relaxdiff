# RelaxDiff — MVP 项目规划

## 项目定位

**一句话**：给两个晶体结构，输出一份带 3D 交互、几何 diff、自动诊断和 LLM 解释的 self-contained HTML 报告。

**形态**：Python package + CLI + 静态报告生成器。无后端、无数据库、无前端框架。

**用户与场景**：跑完 VASP / QE / ML potential relax 的科研用户,想快速判断"这次优化是否合理、有没有异常"。

**差异化**：现有工具是 trajectory player(让你看),它是 sanity checker(告诉你哪里不对)。

**反范围**(明确不做):
- 不做通用 viewer(matterviz 已经过剩)
- 不做 MD 缺陷分析(OVITO 已经成熟)
- 不做 VESTA 插件(VESTA 无插件 API)
- 不做实时 viewer / Jupyter widget(CLI + 静态 HTML 更好分享)

---

## 系统数据流

```
两个结构文件
   ↓ io
[Structure_before, Structure_after]
   ↓ matching            site mapping (idx_before → idx_after)
[SiteMapping]
   ↓ geometry            displacement / bond / coordination / cell
[GeometryDiff]
   ↓ symmetry            spglib 对称性变化
[SymmetryDiff]
   ↓ diagnose            规则引擎 → severity-tagged findings
[DiagnosisReport (JSON)]
   ↓ narrative           Claude API,只读 JSON,不读结构
[Narrative (markdown)]
   ↓ render              Jinja2 + 3Dmol.js inline
report.html
```

**关键设计原则**：
1. 每一层只依赖上一层的输出,**LLM 永远只读 structured JSON**,杜绝它直接解释原子坐标产生幻觉。
2. 所有中间产物都可单独 dump 成 JSON,便于调试和测试。
3. 报告 HTML self-contained,所有结构数据、JS 库 inline,单文件即可分享。

---

## 模块拆解

### M1 · I/O (`relaxdiff/io.py`)
- 支持格式: POSCAR / CIF / extxyz / ASE Atoms / pymatgen JSON
- 一个函数: `load(path_or_obj) -> Structure`
- 用 pymatgen 现成 parser

### M2 · Site Matching (`relaxdiff/matching.py`)
- 主路径: pymatgen `StructureMatcher.get_s2_like_s1()`
- Fallback: 按元素分组 + Hungarian assignment

### M3 · Geometry Diff (`relaxdiff/geometry.py`)
| 子项 | 用什么 |
|---|---|
| Per-atom displacement | M2 的 displacements |
| Bond list | `CrystalNN` 找邻居 |
| Bond length deltas | 配对前后 bond list |
| Bond breaking / forming | 集合差 |
| Coordination number change | `CrystalNN.get_cn()` |
| Local env fingerprint | `LocalStructOrderParams` |
| Cell parameter change | a/b/c/α/β/γ/V |
| Strain tensor | F = A_after @ A_before⁻¹ 极分解 |

### M4 · Symmetry (`relaxdiff/symmetry.py`)
- spglib `get_symmetry_dataset()`
- 比较 space group / point group / Wyckoff
- 容差扫描 `symprec` ∈ {1e-5, 1e-3, 1e-2, 1e-1}

### M5 · Diagnosis Engine (`relaxdiff/diagnose.py`)
| Rule | Trigger | Severity |
|---|---|---|
| `large_displacement` | max_disp > 0.5 Å | warn |
| `runaway_atom` | max_disp > 2.0 Å 且 z-score > 3 | alert |
| `cell_collapse` | ΔV / V < -15% | alert |
| `cell_expansion` | ΔV / V > 15% | warn |
| `symmetry_broken` | space group number 降低 | info / warn |
| `symmetry_elevated` | space group number 提高 | info |
| `bond_breaking` | bonds_broken 非空 | warn |
| `bond_forming` | bonds_formed 非空 | warn |
| `coordination_change` | 任一原子 CN 变化 | warn |
| `large_shear` | strain 非对角分量大 | warn |
| `normal_relaxation` | 全部 below threshold | ok |

### M6 · Narrative (`relaxdiff/narrative.py`)
- Claude Haiku 4.5
- Prompt 只读 structured JSON,不读坐标
- Few-shot 2-3 个例子
- Fallback: 无 API key 时用模板生成

### M7 · Renderer (`relaxdiff/render.py`)
- Jinja2 模板
- 3Dmol.js 内联 (单 script,~700KB)
- vanilla JS + Alpine.js,不上 React
- 输出 self-contained HTML

### M8 · CLI (`relaxdiff/cli.py`)
```bash
relaxdiff before.vasp after.vasp \
  -o report.html \
  --title "..." \
  --no-llm \
  --json report.json
```

### M9 · Demo Gallery
- 4 个预生成报告 + landing page
- GitHub Pages 部署

---

## 4 个 Showcase Case

| Case | 来源 | Wow Point |
|---|---|---|
| 正常 MgO relax | MP `mp-1265` + rattle + MACE | 基线,green 标签 |
| SrTiO3 octahedral tilting | MP 两个 polymorph | 键角变化清晰,diff 视图天然好看 |
| Cell collapse 失败 | 故意放大 cell 后 MACE relax | red alert,narrative 解释 |
| TiO2 anatase → rutile | MP `mp-390` + `mp-2657` | phase transition,LLM 真正发挥价值 |

---

## 项目结构

```
relaxdiff/
├── pyproject.toml
├── README.md
├── PLAN.md
├── relaxdiff/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── io.py
│   ├── matching.py
│   ├── geometry.py
│   ├── symmetry.py
│   ├── diagnose.py
│   ├── narrative.py
│   ├── render.py
│   ├── prompts/
│   │   ├── system.md
│   │   └── examples.json
│   └── templates/
│       ├── report.html.j2
│       ├── style.css
│       └── viewer.js
├── examples/
│   ├── data/
│   └── build.py
├── docs/                  # GitHub Pages
├── tests/
└── scripts/
    └── fetch_mp_examples.py
```

---

## 依赖

```toml
dependencies = [
  "pymatgen>=2024",
  "ase>=3.22",
  "spglib>=2.0",
  "numpy",
  "scipy",
  "jinja2",
  "typer",
  "anthropic",
]

[project.optional-dependencies]
demo = ["mp-api", "mace-torch"]
```

---

## 关键技术决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 3D viewer | 3Dmol.js | 单 script、CIF 原生支持、自带箭头 API |
| 前端框架 | vanilla + Alpine | self-contained,React 太重 |
| LLM | Claude Haiku 4.5 | 便宜、快、能 follow JSON |
| 输出 | 静态 HTML | 易分享、易传播 |
| 测试范围 | matching + geometry + diagnose | deterministic 核心 |

---

## MVP 验收

- [ ] 任意两个同组分 CIF 跑通,不崩溃
- [ ] Report 双击能开,3D viewer 可交互
- [ ] 4 个 demo 都有 findings + narrative
- [ ] `--no-llm` 模式跑通
- [ ] README 有 hero GIF + 4 个 demo 直链

---

## 推后(不在 MVP)

- 多帧 trajectory
- 不同组分对比
- 用户自定义规则
- Jupyter widget
- AI agent 问答
