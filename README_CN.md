# EveryStep：路径追踪 Agentic Workflow

**将蒙特卡洛光线传输理论应用于 LLM Agent 可靠性优化**

> *"我不在意一件事情的概率所带来的不确定性，我在意的是多次做这件事情带来的确定的、极低的失败率。"*
> — 每一个蒙特卡洛渲染器的核心哲学

[English Version](README.md) | [LaTeX 论文](paper/main.tex)

---

## 摘要

大语言模型常因其随机性被质疑——每次调用都是"抽卡"。本文论证：这种批评虽然对单次调用成立，但从根本上误解了问题。**路径追踪面临完全相同的挑战，而且已经解决了它。** 路径追踪图像中的每一个像素都是数千次随机采样的产物，但最终图像收敛于真实解。关键不在于消除随机性，而在于*工程化地驾驭随机性*。

我们提出蒙特卡洛光线传输算法到 LLM Agentic Workflow 的形式化映射，基于三个核心洞察：

1. **LLM 的不可靠性本质上是方差问题**，而计算机图形学已有 60 余年的方差优化经验。
2. **点光源定理**：某些任务的正确答案在输出空间中占据零测集——无论采样多少次都找不到。Next Event Estimation (NEE) 提供了原理性的解法，直接对应于 RAG 和工具调用。
3. **采样效率** $\eta_M = -\ln(1-p_M)/C_M$ 给出了"低成本模型多次采样何时优于高成本模型少次采样"的精确判据。

我们推导了 **Agent 质量方程**（渲染方程的类比），形式化了六种方差优化技术（NEE、MIS、俄罗斯轮盘、重要性采样、MLT、路径空间 MIS），并设计了验证实验。

---

## 目录

- [1. 引言](#1-引言)
- [2. 数学基础](#2-数学基础)
- [3. 核心算法：从路径追踪到 Agentic Workflow](#3-核心算法从路径追踪到-agentic-workflow)
- [4. 点光源定理](#4-点光源定理)
- [5. 概念映射表](#5-概念映射表)
- [6. 相关工作](#6-相关工作)
- [7. 实验设计](#7-实验设计)
- [8. 讨论](#8-讨论)
- [9. 路线图](#9-路线图)
- [参考文献](#参考文献)

---

## 1. 引言

### 1.1 "抽卡"批评

一种流行的观点认为：由于 LLM 的输出是从概率分布中采样的，结果天然不可靠。如果单次调用产出正确结果的概率为 $p$，那么信任单次调用就意味着接受 $1-p$ 的失败率。

这个论证对单次采样而言是数学正确的。

### 1.2 路径追踪：同一个问题，已被解决

路径追踪通过向场景发射随机光线来计算全局光照。每一条光线都是真实辐射度的一个有噪估计。单次采样的图像和随机噪声无异。然而现代路径追踪器能产出照片级真实的图像，因为：

$$P(\text{经过 } N \text{ 次独立采样仍然失败}) = (1 - p)^N$$

当 $p = 0.5$，$N = 10$ 时：$(1 - 0.5)^{10} = 0.000977$，成功率 **99.9%**。

但路径追踪远不止简单的重复采样。过去六十年间，渲染社区开发了丰富的方差优化技术——重要性采样、多重重要性采样（MIS）、下一事件估计（NEE）、俄罗斯轮盘、Metropolis 光线传输（MLT）——每种技术在特定条件下都有可证明的更优收敛性。

### 1.3 核心命题

我们提出：蒙特卡洛光线传输的算法框架可以**直接迁移**到 LLM Agentic Workflow。具体验证：

1. 路径追踪算法和蒙特卡洛哲学能否系统性地提升工业级 Agent 性能？
2. 哪些渲染概念映射到哪些 Agent 概念？类比在哪里失效？
3. 方差优化技术能否使低成本模型在固定预算下优于高成本模型？
4. 这些优化是否跨模态、跨任务类型通用？

### 1.4 为什么选择 Art Bible 生成？

Art Bible（美术圣经）——创意项目的综合视觉风格指南——是我们的主要实验对象，因为：

- 它是一个**长链随机过程**：世界观 → 色彩规范 → 材质细节 → 角色设计 → 环境规则 → …
- 每一步都依赖所有前序步骤（路径依赖性）。
- 正确性由一个**范围**而非单点定义，类比漫反射表面。
- 最终文档必须**全局一致**，对累积误差敏感——类比渲染中的能量守恒。

---

## 2. 数学基础

### 2.1 渲染方程

Kajiya (1986) 提出的渲染方程是光线传输的基本模型：

$$L_o(\mathbf{x}, \omega_o) = L_e(\mathbf{x}, \omega_o) + \int_{\Omega} f_r(\mathbf{x}, \omega_i, \omega_o) \, L_i(\mathbf{x}, \omega_i) \, (\omega_i \cdot \mathbf{n}) \, d\omega_i$$

其中：
- $L_o(\mathbf{x}, \omega_o)$：点 $\mathbf{x}$ 处沿 $\omega_o$ 方向的出射辐射度
- $L_e(\mathbf{x}, \omega_o)$：自发光辐射度
- $f_r(\mathbf{x}, \omega_i, \omega_o)$：双向反射分布函数（BRDF）
- $L_i(\mathbf{x}, \omega_i)$：来自 $\omega_i$ 方向的入射辐射度
- $(\omega_i \cdot \mathbf{n})$：余弦衰减项
- $\Omega$：表面上方的半球方向空间

### 2.2 Agent 质量方程

我们提出 **Agent 质量方程**作为直接类比：

$$Q(s_k) = Q_{\text{direct}}(s_k) + \int_{\mathcal{A}} T(s_k, a) \, Q(s_{k+1}(a)) \, p(a \mid s_k) \, da$$

| 渲染方程 | Agent 质量方程 | 角色 |
|---|---|---|
| $L_o(\mathbf{x}, \omega_o)$ | $Q(s_k)$ | 当前状态的总质量 |
| $L_e(\mathbf{x}, \omega_o)$ | $Q_{\text{direct}}(s_k)$ | 当前步骤的直接质量贡献 |
| $f_r(\mathbf{x}, \omega_i, \omega_o)$ | $T(s_k, a)$ | 传递函数：action $a$ 如何传递质量 |
| $L_i(\mathbf{x}, \omega_i)$ | $Q(s_{k+1}(a))$ | 后续步骤的质量 |
| $(\omega_i \cdot \mathbf{n}) \, d\omega_i$ | $p(a \mid s_k) \, da$ | LLM 对 action 的概率分布 |
| $\Omega$ | $\mathcal{A}$ | Action 空间 |

递归结构完全一致：总质量 = 直接贡献 + 对所有可能后续的积分（以传递函数和概率测度加权）。

### 2.3 路径积分形式

沿用 Veach (1997) 的路径积分表述。渲染路径 $\bar{x} = (x_0, x_1, \ldots, x_K)$ 的贡献为：

$$I = \int_{\bar{\Omega}} f(\bar{x}) \, d\mu(\bar{x})$$

类比地，**Agent 执行路径** $\bar{p} = (s_0, a_0, s_1, a_1, \ldots, s_K)$ 的贡献为：

$$\mathcal{Q} = \int_{\bar{\mathcal{P}}} F(\bar{p}) \, d\nu(\bar{p})$$

其中：
- $\bar{\mathcal{P}}$：所有可能的 Agent 执行路径空间
- $F(\bar{p}) = Q_{\text{final}}(\bar{p}) \cdot \prod_{k=0}^{K-1} T(s_k, a_k)$：路径吞吐量（最终质量 × 沿路径所有传递函数之积）
- $d\nu(\bar{p}) = \prod_{k=0}^{K-1} p(a_k \mid s_k) \, da_k$：LLM 诱导的路径概率测度

### 2.4 蒙特卡洛估计与方差

对 $\mathcal{Q}$ 的基础蒙特卡洛估计：

$$\hat{\mathcal{Q}}_N = \frac{1}{N} \sum_{i=1}^{N} \frac{F(\bar{p}_i)}{p(\bar{p}_i)}$$

其中 $\bar{p}_i$ 是从 $p$ 中独立同分布采样的路径。方差为：

$$\operatorname{Var}[\hat{\mathcal{Q}}_N] = \frac{1}{N} \operatorname{Var}\!\left[\frac{F(\bar{p})}{p(\bar{p})}\right] = \frac{\sigma^2}{N}$$

**核心洞察**：方差以 $O(1/N)$ 收敛。将标准差减半需要 $4\times$ 的采样量。这是所有方差优化技术所要突破的基本速率。

### 2.5 方差-成本权衡：采样效率判据

设模型 $M$ 的单次成本为 $C_M$，单次成功概率为 $p_M$。$N$ 次采样后至少一次成功的概率：

$$P_{\text{success}}(N) = 1 - (1 - p_M)^N$$

固定预算 $B$ 下可承受的采样次数为 $N = \lfloor B / C_M \rfloor$。比较小模型 $M_s$ $(p_s, C_s)$ 与大模型 $M_l$ $(p_l, C_l)$，当以下条件成立时 $M_s$ 占优：

$$1 - (1 - p_s)^{B/C_s} > 1 - (1 - p_l)^{B/C_l}$$

取对数：

$$\frac{\ln(1 - p_s)}{C_s} < \frac{\ln(1 - p_l)}{C_l}$$

定义**采样效率**：

$$\boxed{\eta_M = \frac{-\ln(1 - p_M)}{C_M}}$$

当 $p_M \ll 1$ 时简化为 $\eta_M \approx p_M / C_M$，即直觉上的"每美元精度"。**在固定预算下，$\eta$ 更高的模型总是更优，无论单次精度如何。**

这从理论上形式化了 Brown et al. (2024, "Large Language Monkeys") 的实证发现：5 个小模型采样可以胜过 1 个 GPT-4o 采样，不是因为小模型更聪明，而是因为 $\eta_{\text{small}} > \eta_{\text{large}}$。

---

## 3. 核心算法：从路径追踪到 Agentic Workflow

### 3.1 Next Event Estimation (NEE) —— 解决点光源问题

#### 渲染中的问题

点光源在立体角空间中占据零测度：

$$\mu\bigl(\{\omega \in \Omega : \omega \text{ 命中点光源}\}\bigr) = 0$$

无论追踪多少条随机光线，**没有任何一条**会找到光源。图像永远是黑的。这不是收敛问题——这是测度论意义上的不可能。

NEE 通过在每个着色点**显式采样光源**来解决：

$$\hat{L}_{\text{NEE}}(\mathbf{x}) = \sum_{l \in \mathcal{L}} \frac{f_r(\mathbf{x}, \omega_l, \omega_o) \, L_e(\mathbf{x}_l) \, G(\mathbf{x}, \mathbf{x}_l)}{p_{\text{light}}(\mathbf{x}_l)} \cdot V(\mathbf{x}, \mathbf{x}_l)$$

其中：
- $\mathcal{L}$：光源集合
- $G(\mathbf{x}, \mathbf{x}_l) = \frac{|\cos\theta_x||\cos\theta_l|}{||\mathbf{x} - \mathbf{x}_l||^2}$：几何项
- $V(\mathbf{x}, \mathbf{x}_l) \in \{0, 1\}$：可见性函数（阴影光线）
- $p_{\text{light}}$：光源表面上的采样 PDF

#### Agent 类比

在 Agentic Workflow 中，"点光源"是正确答案在输出空间中占据零测集（或近零测度）的任务：

- 需要精确参数语法的 API 调用
- 必须严格符合 schema 的 JSON 输出
- 需要精确数值的计算结果
- 必须编译通过且通过测试的代码片段

对于这些任务：

$$\mu\bigl(\{a \in \mathcal{A} : a \text{ 是正确的}\}\bigr) \approx 0$$

**NEE-Agent** 显式连接到已知正确的参考源：

$$\hat{Q}_{\text{NEE}}(s_k) = Q_{\text{direct}}(s_k) + \frac{T(s_k, a^{\ast}) \, Q^{\ast}(s_{k+1})}{p_{\text{ref}}(a^{\ast})} \cdot \mathbb{1}[\operatorname{valid}(a^{\ast}, s_k)]$$

其中 $a^{\ast}$ 来自参考分布 $p_{\text{ref}}$——RAG 知识库、工具/API 调用结果、或经过验证的先例。指示函数 $\mathbb{1}[\operatorname{valid}(a^{\ast}, s_k)]$ 充当阴影光线：检查参考 action 是否与当前状态兼容。

### 3.2 Multiple Importance Sampling (MIS)

#### Veach 的 Balance Heuristic

当组合 $n$ 种采样策略，每种产生 $n_i$ 个来自分布 $p_i$ 的样本时：

$$\hat{F}_{\text{MIS}} = \sum_{i=1}^{n} \frac{1}{n_i} \sum_{j=1}^{n_i} w_i(X_{i,j}) \, \frac{f(X_{i,j})}{p_i(X_{i,j})}$$

Balance heuristic 权重函数：

$$w_i(x) = \frac{n_i \, p_i(x)}{\sum_{k=1}^{n} n_k \, p_k(x)}$$

**Veach 方差界定理**：对于总采样数为 $\sum_i n_i = N$ 的 balance heuristic 估计器：

$$\operatorname{Var}[\hat{F}_{\text{MIS}}] \leq \frac{1}{\min_i n_i} \left(\int \lvert f(x) \rvert \, dx\right)^{\!2}$$

这保证了无论被积函数如何，MIS 不会比最优单策略差太多。

**Power heuristic**（指数 $\beta$，通常 $\beta = 2$）在实践中常有更好表现：

$$w_i^{(\beta)}(x) = \frac{\bigl(n_i \, p_i(x)\bigr)^\beta}{\sum_{k=1}^{n} \bigl(n_k \, p_k(x)\bigr)^\beta}$$

#### Agent MIS

我们识别了 Agent 任务的三种基本采样策略（类比渲染中的 BSDF 采样 + 光源采样）：

| 策略 | 渲染类比 | Agent 实现 | 擅长场景 |
|---|---|---|---|
| $p_1$：自由生成 | BSDF 采样 | LLM 自由生成 | 覆盖广泛输出空间 |
| $p_2$：引导生成 | 光源采样 / NEE | RAG 增强生成 | 瞄准已知正确区域 |
| $p_3$：确定性工具 | Delta 分布（点光源） | API/工具调用 | 结构化查询的精确答案 |

MIS 估计器：

$$\hat{Q}_{\text{MIS}}(s_k) = \sum_{i=1}^{3} \frac{1}{n_i} \sum_{j=1}^{n_i} \frac{n_i \, p_i(a_{i,j})}{\sum_{m=1}^{3} n_m \, p_m(a_{i,j})} \cdot \frac{F(a_{i,j})}{p_i(a_{i,j})}$$

**关键优势：MIS 自动将功劳分配给最适合每个样本的策略。** 当任务是"漫反射"的（多个有效答案），自由生成主导。当任务是"点光源"（唯一精确答案），工具调用主导。MIS 无需手动调参即可处理整个光谱。

### 3.3 俄罗斯轮盘 (Russian Roulette) —— 无偏路径终止

路径追踪中，在第 $k$ 次弹射处，累积吞吐量为 $\beta_k$：

$$\hat{L} = \begin{cases} \dfrac{L_{\text{continued}}}{q_k} & \text{以概率 } q_k \\[6pt] 0 & \text{以概率 } 1 - q_k \end{cases}$$

**无偏性证明**：$E[\hat{L}] = q_k \cdot \frac{L}{q_k} + (1 - q_k) \cdot 0 = L$。

存活概率通常设为 $q_k = \min(\lVert\beta_k\rVert, 1)$。

#### Agent 俄罗斯轮盘

在 Agent 链的第 $k$ 步，**Validator Agent** 评估当前路径的部分质量 $Q_k \in [0, 1]$：

$$q_k = \min\!\left(\frac{Q_k}{Q_{\text{threshold}}}, \, 1\right)$$

如果 Validator 判断路径正在走向低质量区域，则以概率性方式终止该路径。存活路径通过除以 $q_k$ 来上调权重，保持无偏性。

**性质**：
- 零系统偏差——只增加方差（且仅对本来就可能失败的路径增加方差）。
- 期望 token 节省：$Q_k \ll Q_{\text{threshold}}$ 的路径以高概率被提前终止，节省所有后续步骤的成本。
- 方差增量有界：$\operatorname{Var}_{\text{RR}} \leq \operatorname{Var}_{\text{no-RR}} \cdot (1/q_k - 1)$，当 $q_k$ 接近 1 时（即好路径）增量很小。

### 3.4 重要性采样 (Importance Sampling) —— 引导生成

使方差最小化到零的最优 IS PDF：

$$q^{\ast}(x) = \frac{\lvert f(x) \rvert \, p(x)}{\int \lvert f(x') \rvert \, p(x') \, dx'}$$

实践中无法实现（需要已知被积函数），但近似也能带来巨大的方差优化。

#### 通过约束缓冲区实现 Agent 重要性采样

我们引入**约束缓冲区（Constraint Buffer）**——从前序步骤中提取"视觉锚点"的结构化表示：

1. 在步骤 $k$ 之后，提取关键约束：$\mathcal{C}_k = \{c_1, c_2, \ldots, c_m\}$（如："末世废土"、"霓虹灯光"、"高对比度"）
2. 将约束编码进步骤 $k+1$ 的 prompt，偏置 LLM 分布：

$$p_{\text{guided}}(a \mid s_{k+1}) \propto p_{\text{LLM}}(a \mid s_{k+1}) \cdot \prod_{j=1}^{m} \phi(a, c_j)$$

其中 $\phi(a, c_j) \geq 0$ 是 action $a$ 与约束 $c_j$ 之间的相容性评分。

这通过将 LLM 的输出分布集中到高期望质量的区域，近似了重要性采样——即对被积函数的"明亮方向"进行集中采样。

### 3.5 Metropolis Light Transport (MLT) —— MCMC 迭代精修

给定当前路径 $\bar{p}$（质量 $F(\bar{p})$），提出变异 $\bar{p}' \sim T(\bar{p}' \mid \bar{p})$。以 Metropolis-Hastings 概率接受：

$$\alpha(\bar{p}' \mid \bar{p}) = \min\!\left(1, \, \frac{F(\bar{p}') \, T(\bar{p} \mid \bar{p}')}{F(\bar{p}) \, T(\bar{p}' \mid \bar{p})}\right)$$

对于对称提案 $T(\bar{p}' \mid \bar{p}) = T(\bar{p} \mid \bar{p}')$，简化为：

$$\alpha(\bar{p}' \mid \bar{p}) = \min\!\left(1, \, \frac{F(\bar{p}')}{F(\bar{p})}\right)$$

#### Agent MLT：基于变异的文档精修

以 Art Bible 等复杂文档为例：

1. **初始化**：使用标准路径追踪（多次采样 + MIS）生成初始草稿 $\bar{p}_0$。
2. **变异**：选择单个章节，要求 LLM 修订 → $\bar{p}'$。
3. **评估**：对变异后文档 $F(\bar{p}')$ 进行全局一致性 + 章节质量评分。
4. **接受/拒绝**：应用 Metropolis-Hastings 准则。
5. **迭代**：从步骤 2 重复。

这对 Art Bible 特别强大，因为：
- 局部修改有全局影响（改变色彩规范影响所有后续章节）。
- MLT 自然地在好解的邻域中探索，而非从头重来。
- 马尔科夫链收敛到正比于 $F$ 的平稳分布，意味着它在文档空间的高质量区域停留更多时间。

### 3.6 路径空间 MIS：多策略合成

在产品级渲染器中，不同技术擅长不同的传输现象：

| 传输现象 | 最佳技术 | Agent 类比 |
|---|---|---|
| 漫反射间接光照 | 路径追踪 | 自由头脑风暴 |
| 焦散 (SDS 路径) | 光子映射 / MLT | 约束引导搜索 |
| 直接光照 | NEE | RAG / 工具调用 |
| 镜面反射链 | 双向路径追踪 | 多 Agent 协作 |

路径空间 MIS 用可证明最优的权重组合所有估计器。在 Agent 语境中，这意味着**并行运行多条不同策略的 Agent 管线，然后用 MIS 权重合成结果。**

---

## 4. 点光源定理

这是本框架最锋利的理论贡献。

### 4.1 定义

**定义 1（Agent 点光源）。** 若任务的正确输出集 $\mathcal{A}^{\ast} \subset \mathcal{A}$ 满足：

$$\mu(\mathcal{A}^{\ast}) = 0$$

其中 $\mu$ 是 LLM 输出分布 $p(\cdot \mid s)$ 诱导的测度，则称该任务具有*点光源性质*。

更实用地说，如果 $\mu(\mathcal{A}^{\ast}) < \epsilon$（某个极小的 $\epsilon \ll 1$），则称该任务为 $\epsilon$-点光源。

**定义 2（任务反射光谱）。** 我们沿连续谱对任务进行分类：

| BRDF 类型 | $\mu(\mathcal{A}^{\ast})$ | 示例 |
|---|---|---|
| 完全漫反射 | $\mu(\mathcal{A}^{\ast}) \approx \mu(\mathcal{A})$ | "写一首关于秋天的诗" |
| 光泽反射 | $0 < \mu(\mathcal{A}^{\ast}) \ll \mu(\mathcal{A})$ | "为赛博朋克游戏写 Art Bible" |
| 完全镜面反射 | $\mu(\mathcal{A}^{\ast})$ 为单点 | "$\int_0^1 x^2 dx$ 等于多少？" |
| 点光源 (delta) | $\mu(\mathcal{A}^{\ast}) = 0$ | "调用 `POST /api/v2/users` 并使用精确的 JSON schema" |

### 4.2 定理

**定理 1（纯采样不可达性）。** 对于具有点光源性质的任务，朴素蒙特卡洛估计器 $\hat{Q}_N$ 满足：

$$P\!\left(\exists\, i \leq N : a_i \in \mathcal{A}^{\ast}\right) = 0 \quad \text{对所有 } N \in \mathbb{N}$$

当 $a_i \sim p(\cdot \mid s)$ 且 $\mu(\mathcal{A}^{\ast}) = 0$ 时成立。

*证明。* 每个 $a_i$ 从 $p(\cdot \mid s)$ 独立抽取，后者诱导测度 $\mu$。由 $\mu(\mathcal{A}^{\ast}) = 0$，对每个 $i$ 有 $P(a_i \in \mathcal{A}^{\ast}) = 0$。由可数次可加性：

$$P\!\left(\bigcup_{i=1}^{N} \{a_i \in \mathcal{A}^{\ast}\}\right) \leq \sum_{i=1}^{N} P(a_i \in \mathcal{A}^{\ast}) = 0 \qquad \square$$

**定理 2（NEE 可达性）。** 若存在参考分布 $p_{\text{ref}}$ 使得 $p_{\text{ref}}(\mathcal{A}^{\ast}) > 0$，则 NEE-Agent 估计器满足：

$$E\!\left[\hat{Q}_{\text{NEE}}\right] > 0 \quad \text{且} \quad \operatorname{Var}\!\left[\hat{Q}_{\text{NEE}}\right] < \infty$$

*证明概要。* NEE 估计器从 $p_{\text{ref}}$ 抽取 $a^{\ast}$ 并计算 $T(s, a^{\ast}) Q^{\ast}(s') / p_{\text{ref}}(a^{\ast})$。由于 $p_{\text{ref}}(\mathcal{A}^{\ast}) > 0$，样本 $a^{\ast}$ 以正概率落入 $\mathcal{A}^{\ast}$。因为对正确 action 有 $T > 0$ 和 $Q^{\ast} > 0$，期望严格为正。当 $p_{\text{ref}}$ 在 $\mathcal{A}^{\ast}$ 上有支撑时，$T \cdot Q^{\ast} / p_{\text{ref}}$ 有界保证了有限方差。$\square$

**推论（NEE 对点光源任务的必要性）。** 对于 $\mu(\mathcal{A}^{\ast}) = 0$ 的任务，NEE 式直接采样（RAG、工具调用、经验证的参考）不仅是优化手段——它是**非零期望质量的必要条件**。

### 4.3 MIS 桥梁

在渲染中，MIS 优雅地处理了同时包含漫反射表面和点光源的场景：BSDF 采样（擅长漫反射）与光源采样/NEE（点光源必需）的组合，balance heuristic 自动将零概率策略的贡献归零。

类比地，**Agent MIS 自动处理整个任务反射光谱。** 对于漫反射任务（多个有效输出），自由生成主导 MIS 权重。对于点光源任务（精确答案），工具调用主导。无需手动分类任务——MIS 权重自适应。

这可能是最强大的实践意义：一个正确配置的 MIS Agent 管线能**最优地处理所有任务类型**，正如启用了 MIS 的路径追踪器能处理所有材质类型。

---

## 5. 概念映射表

| 路径追踪概念 | 数学定义 | Agent 概念 | 数学定义 | 工程实现 |
|---|---|---|---|---|
| 光线 | $r(t) = \mathbf{o} + t\mathbf{d}$ | 单次 Agent 调用 | $a \sim p(\cdot \mid s)$ | 一次 LLM API 调用 |
| 路径 | $\bar{x} = (x_0, \ldots, x_K)$ | Agent 执行链 | $\bar{p} = (s_0, a_0, \ldots, s_K)$ | 多步工作流 |
| 辐射度 | $L(\mathbf{x}, \omega)$ | 输出质量 | $Q(s)$ | 质量评分函数 |
| BRDF | $f_r(\mathbf{x}, \omega_i, \omega_o)$ | 传递函数 | $T(s, a)$ | 质量传播模型 |
| 渲染方程 | 见 §2.1 | Agent 质量方程 | 见 §2.2 | 递归质量评估 |
| SPP（每像素采样数） | $N$ 条光线/像素 | 每任务采样数 | $N$ 次调用/任务 | 并行 API 调用 |
| 点光源 | $\mu = 0$（$\Omega$ 中） | 精确答案任务 | $\mu(\mathcal{A}^{\ast}) = 0$ | 结构化输出、API 调用 |
| NEE / 直接光照采样 | 显式光源连接 | 参考引导生成 | RAG + 工具调用 | 检索增强生成 |
| BSDF 采样 | 采样 $\omega_i \sim f_r$ | 自由生成 | 采样 $a \sim p_{\text{LLM}}$ | 标准 prompting |
| MIS | 加权组合 | 多策略采样 | 加权组合 | 并行策略 + 融合 |
| 俄罗斯轮盘 | 随机终止 | 基于 Validator 的剪枝 | 质量驱动的提前停止 | Validator Agent |
| 重要性采样 | 引导 PDF 向 $f$ 靠拢 | 约束引导生成 | 约束缓冲区 | 结构化 prompting |
| MLT | MCMC 路径变异 | 迭代文档精修 | 局部修改 + 接受/拒绝 | 逐章节修订循环 |
| BVH / 加速结构 | 空间索引 | 知识索引 | 向量数据库 | RAG 基础设施 |
| 环境贴图 | 预计算光照 | 参考知识库 | 经整理的范例 | 微调模型、风格指南 |
| 降噪 | 后处理噪声去除 | 结果精修 | 合成 Agent | 最终质量通过 |
| 能量守恒 | $\int f_r \, d\omega \leq 1$ | 质量单调性 | $T(s,a) \leq 1$ | 验证约束 |

---

## 6. 相关工作

### 6.1 推理时计算扩展 (Test-Time Compute Scaling)

- **Brown et al., "Large Language Monkeys" (arXiv:2407.21787)**：核心发现——DeepSeek 在 SWE-bench 上从 1 次采样的 15.9% 扩展到 250 次的 56%。小模型 5 次采样优于 GPT-4o 单次。覆盖率遵循 log-linear 扩展律。
- **"The Art of Scaling Test-Time Compute" (arXiv:2512.02008)**：大规模实证研究（30B+ tokens，8 个 LLM），发现没有单一策略普遍占优。
- **"A Survey on Test-Time Scaling in LLMs" (arXiv:2503.24235)**：全面分类体系：扩展*什么*（内部/顺序/并行/混合），*如何*（RL/SFT），*在哪里*（推理/通用），*效果如何*（评估）。

### 6.2 LLM 中的蒙特卡洛方法

- **"Rollout Roulette" (arXiv:2502.01618)**：基于粒子的蒙特卡洛推理扩展，比确定性搜索快 4–16×。Qwen2.5-Math-1.5B 4 次 rollout 即匹配 GPT-4o。
- **"Monte Carlo Temperature" (arXiv:2502.18389)**：鲁棒的温度校准，无需昂贵的超参搜索。
- **DR-MCTS**：双稳健离策略估计整合 MCTS，3× 成功率 + 50% 成本降低。

### 6.3 MCTS 用于 Agent 推理

- **Empirical-MCTS (arXiv:2602.04248)**：双循环 MCTS + 跨问题的全局记忆库 + 元提示系统 prompt 演化。
- **AB-MCTS (arXiv:2503.04412)**：自适应分支——基于外部反馈信号动态决定"更宽"还是"更深"。
- **CMCTS (2025)**：约束 MCTS 用于数学推理——7B 模型达到 83.4% 精度，超越 72B 基线。

### 6.4 MCMC 用于文本生成与优化

- **POLCA (arXiv:2603.14769)**：将 LLM 优化建模为具有探索-利用权衡的随机生成优化。
- **MHLP**：通过 LLM 提案的 Metropolis-Hastings——将 prompt 视为贝叶斯参数。
- **Discrete Auto-regressive Biasing (arXiv:2502.03685)**：结合梯度离散 MCMC 与自回归扰动的 Langevin-within-Gibbs 采样。

### 6.5 Agent 可靠性与验证

- **Sherlock (arXiv:2511.00330)**：基于反事实分析的选择性验证——精度提升 18.3%，时间降低 48.7%，成本降低 26%（对比蒙特卡洛搜索）。
- **CISC**：置信度自一致性——所需采样减少 40%+，8 个样本匹配 30 个样本的性能。
- **SSR (Socratic Self-Refine)**：通过受控重解的步骤级验证——67.57% 的相对提升。

### 6.6 多 Agent 并行工作流

- **Fork-Merge 模式**：Anthropic 的并行子 Agent 架构，性能提升 90.2%。
- **OrchMAS (arXiv:2603.03005)**：双层编排 + 异构 LLM 整合 + 动态重规划。
- **TOA**：基于树搜索的编排 Agent，整合 MCTS 与奖励模型用于多模型对齐合成。

### 6.7 基础参考文献

- **Kajiya, J. T. (1986)**，"The rendering equation." *SIGGRAPH*。
- **Veach, E. (1997)**，"Robust Monte Carlo Methods for Light Transport Simulation." *博士论文，Stanford University*。
- **Veach, E. & Guibas, L. J. (1995)**，"Optimally combining sampling techniques for Monte Carlo rendering." *SIGGRAPH*。

---

## 7. 实验设计

### 实验零：点光源验证

**假设**：对于正确答案集近零测度的任务，NEE 式方法（RAG + 工具）是必需的，而纯随机采样无论 $N$ 多大都会失败。

| 参数 | 取值 |
|---|---|
| 任务 | 严格 JSON schema 生成、精确 API 调用构造 |
| 方法 | 纯采样 ($N = 1, 10, 100, 1000$)、仅 NEE、MIS（采样 + NEE） |
| 模型 | GPT-4o-mini、Claude Haiku、Gemini Flash |
| 指标 | 精确匹配率、schema 验证通过率 |

**预期结果**：纯采样在 0% 附近停滞。NEE 在 $N=1$ 时即达到高精度。MIS 在点光源任务上匹配 NEE，在混合任务上优于 NEE。

### 实验一：基础蒙特卡洛——重复采样

**假设**：质量随 $\sqrt{N}$ 可预测地收敛，符合渲染类比。

| 参数 | 取值 |
|---|---|
| 任务 | 简化 Art Bible 章节（色彩规范） |
| $N$ | 1, 4, 16, 64, 256 |
| 模型 | 小型 (GPT-4o-mini, Haiku, Flash) vs 大型 (GPT-4o, Sonnet, Pro) |
| 选择策略 | Best-of-N（质量评分器）、多数投票 |
| 指标 | 质量评分（LLM 评审）、成本、延迟 |

### 实验二：俄罗斯轮盘剪枝效率

**假设**：RR 在不降低最终质量的前提下减少 token 消耗。

| 参数 | 取值 |
|---|---|
| 任务 | 5 步 Art Bible 链（世界观 → 色彩 → 材质 → 角色 → 环境） |
| 方法 | 无剪枝、RR（$Q_{\text{threshold}} \in \{0.3, 0.5, 0.7\}$） |
| 指标 | Token 消耗、最终质量、完成路径 vs 终止路径 |

### 实验三：通过约束缓冲区的重要性采样

**假设**：约束引导生成比无约束生成收敛更快。

| 参数 | 取值 |
|---|---|
| 任务 | Art Bible 章节生成（以前序章节为条件） |
| 方法 | 无约束、约束缓冲区（从前序步骤提取关键锚点） |
| 指标 | 质量评分方差、收敛速度（达到阈值质量所需采样数） |

### 实验四：MLT 基于变异的精修

**假设**：从好的初始草稿出发的局部扰动优于从零重新生成。

| 参数 | 取值 |
|---|---|
| 任务 | 完整 Art Bible 精修 |
| 方法 | 从零重新生成 ($N$ 次)、MLT (1 次初始 + $N-1$ 次变异) |
| 指标 | $N$ 次 LLM 调用后的质量、全局一致性评分 |

### 实验五：MIS 多策略合成

**假设**：组合自由生成 + RAG + 工具的 MIS 优于任何单一策略。

| 参数 | 取值 |
|---|---|
| 任务 | 混合难度 Art Bible（部分章节漫反射、部分点光源） |
| 方法 | 仅自由 ($N$)、仅 RAG ($N$)、仅工具 ($N$)、MIS (每种 $N/3$ + balance heuristic) |
| 指标 | 总体质量、各章节质量、成本 |

### 实验六：采样效率——小模型 × 多次 vs 大模型 × 少次

**假设**：在固定预算下，存在小模型占优的交叉点。

| 参数 | 取值 |
|---|---|
| 预算 | $\{1, 5, 10, 50\}$ 美元等值 |
| 小模型 | GPT-4o-mini ($C_s$)、Claude Haiku ($C_s'$)、Gemini Flash ($C_s''$) |
| 大模型 | GPT-4o ($C_l$)、Claude Sonnet ($C_l'$)、Gemini Pro ($C_l''$) |
| 任务 | 标准化 Art Bible 生成基准 |
| 指标 | 各预算水平下的质量、实测 $\eta_M$ 值 |

---

## 8. 讨论

### 8.1 类比成立之处

渲染方程 ↔ Agent 质量方程的映射在结构上是精确的。两者都是具有相同递归结构的第二类 Fredholm 积分方程。方差优化技术（MIS、NEE、RR、IS、MLT）都是*算法层面*的构造，仅依赖于积分结构而非物理解释。

### 8.2 类比失效之处

| 渲染性质 | Agent 现实 | 启示 |
|---|---|---|
| 能量守恒 ($\int f_r \leq 1$) | 无保证——LLM 可能"放大"错误 | 可能需要每步显式质量上限 |
| 物理 BRDF 互易性 | 无对应物 | 双向方法可能无法直接迁移 |
| 确定性几何 | 随机状态转移 | 路径概率更难精确计算 |
| 连续输出空间 | 混合连续/离散空间 | 部分测度论结果需要调整 |
| 已知光源位置 | 正确答案位置通常未知 | NEE 需要显式构造 $p_{\text{ref}}$ |

### 8.3 Verifier 的角色

在本框架中，Verifier Agent 映射到路径追踪中的**阴影光线 (shadow ray)**：
- 阴影光线检查某点是否能"看到"光源（可见性测试）。
- Verifier 检查提出的 action 是否与质量目标"兼容"（有效性测试）。
- 两者都是二值函数，控制一个样本是否有贡献。

质量评分器映射到**吞吐量测量**——它为每条路径分配标量值，类比渲染方程如何计算辐射度。

### 8.4 与现有工作的关系

本框架统摄了若干现有方法：

| 现有方法 | 在本框架中的位置 |
|---|---|
| Best-of-N 采样 | 基础蒙特卡洛 + Best-of-N 选择 |
| Self-consistency (Wang et al., 2022) | 蒙特卡洛估计 + 多数投票 |
| Tree-of-Thought | 路径空间中的 MCTS |
| RAG | NEE（显式光源连接） |
| 工具调用 | 点光源直接采样（delta 分布） |
| LangChain Fork-Merge | 并行路径采样 + MIS |
| Sherlock 选择性验证 | 基于反事实的 $q_k$ 的俄罗斯轮盘 |

统一视角是：**所有这些**都是应用于 Agent 质量积分的蒙特卡洛方差优化的特例。

---

## 9. 路线图

### Phase 0：理论基础（当前）
- [x] 概念映射与数学形式化
- [x] 文献调研与定位
- [ ] 完整证明的 LaTeX 论文

### Phase 1：概念验证
- [ ] 实现 Agent 任务的基础蒙特卡洛采样器
- [ ] 在简单任务上验证 $O(1/N)$ 收敛
- [ ] 实现质量评分函数（LLM-as-judge）

### Phase 2：算法实现
- [ ] 带 RAG 集成的 NEE-Agent
- [ ] 使用 balance heuristic 组合自由 + RAG + 工具策略的 MIS
- [ ] 带 Validator Agent 的俄罗斯轮盘
- [ ] 通过约束缓冲区的重要性采样
- [ ] MLT 基于变异的精修

### Phase 3：端到端 Art Bible 管线
- [ ] 使用所有方差优化技术的完整 Art Bible 生成
- [ ] 与基线（单次生成）的实证比较
- [ ] 成本分析与采样效率测量

### Phase 4：框架抽象
- [ ] 提取可复用的 `EveryStep` 框架
- [ ] 推广到 Art Bible 之外的任意多步 Agent 工作流
- [ ] 发表结果并开源框架

---

## 参考文献

1. Kajiya, J. T. (1986). "The rendering equation." *Proceedings of SIGGRAPH '86*, 143–150.
2. Veach, E. (1997). "Robust Monte Carlo Methods for Light Transport Simulation." *博士论文*, Stanford University.
3. Veach, E. & Guibas, L. J. (1995). "Optimally combining sampling techniques for Monte Carlo rendering." *SIGGRAPH '95*, 419–428.
4. Brown, B. et al. (2024). "Large Language Monkeys: Scaling Inference Compute with Repeated Sampling." *arXiv:2407.21787*.
5. Snell, C. et al. (2025). "The Art of Scaling Test-Time Compute for Large Language Models." *arXiv:2512.02008*.
6. Qu, C. et al. (2025). "A Survey on Test-Time Scaling in Large Language Models." *arXiv:2503.24235*.
7. Liang, Z. et al. (2025). "Rollout Roulette: A Probabilistic Inference Approach to Inference-Time Scaling." *arXiv:2502.01618*.
8. Alizadeh, K. et al. (2025). "Monte Carlo Temperature." *arXiv:2502.18389*.
9. Chen, Y. et al. (2026). "Empirical-MCTS: Continuous Agent Evolution via Dual-Experience MCTS." *arXiv:2602.04248*.
10. Putta, P. et al. (2025). "Wider or Deeper? Adaptive Branching Tree Search." *arXiv:2503.04412*.
11. Quaye, J. et al. (2025). "Sherlock: Reliable and Efficient Agentic Workflow Execution." *arXiv:2511.00330*.
12. Li, Z. et al. (2026). "POLCA: Stochastic Generative Optimization with LLM." *arXiv:2603.14769*.
13. Microsoft Research (2025). "Trace: End-to-End Generative Optimization for AI Agents."
14. Chen, X. et al. (2025). "OrchMAS: Orchestrated Multi-Agent Scientific Expert Agents." *arXiv:2603.03005*.
15. Wang, X. et al. (2022). "Self-Consistency Improves Chain of Thought Reasoning in Language Models." *arXiv:2203.11171*.

---

*本项目是连接计算机图形学与 AI Agent 优化之间桥梁的持续研究工作的一部分。我们相信渲染社区数十年积累的随机方法经验，是 AI 时代一个尚未被开发的算法宝库。*
