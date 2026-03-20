---
marp: true
theme: default
math: mathjax
paginate: true
style: |
  section {
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  section.lead h1 {
    font-size: 2.5em;
    text-align: center;
  }
  section.lead p {
    text-align: center;
    font-size: 1.2em;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1em;
  }
  table { font-size: 0.8em; }
  blockquote { border-left: 4px solid #2196F3; padding-left: 1em; font-style: italic; }
---

<!-- _class: lead -->

# EveryStep
## Path Tracing the Agentic Workflow

**Applying Monte Carlo Light Transport Theory
to LLM Agent Reliability Optimization**

March 2026

<!--
PRESENTER NOTES:
Welcome everyone. Today I want to share an idea that connects two seemingly unrelated fields — computer graphics rendering and AI agent systems. I'll show you that the "unreliability" problem of LLMs has already been solved, 60 years ago, by the rendering community.
-->

---

# "LLMs are just gacha pulls."

<br>

> Every output is sampled from a probability distribution.
> You can never *guarantee* a correct result.
> Therefore, you should **not trust** LLMs.

<br>

Is this argument correct?

<!--
PRESENTER NOTES:
There's a popular argument that LLMs are fundamentally unreliable because each call is a random sample. Let me show you why this argument, while correct for a single call, completely misunderstands the situation.
-->

---

# One call = One gacha pull

```
Call 1:  ✗  (wrong format)
Call 2:  ✓  (correct!)
Call 3:  ✗  (hallucinated data)
Call 4:  ✗  (partial answer)
Call 5:  ✓  (correct!)
```

Single-call success probability: $p$

Single-call failure rate: $1 - p$

**The critique is mathematically correct — for $N = 1$.**

<!--
PRESENTER NOTES:
If you only call the model once, yes, you're gambling. Each call independently succeeds with probability p. But what happens when we call it multiple times?
-->

---

# What if we call it $N$ times?

$$P(\text{all } N \text{ fail}) = (1 - p)^N$$

<br>

| $p$ | $N=1$ | $N=5$ | $N=10$ | $N=20$ |
|-----|--------|--------|---------|---------|
| 0.3 | 70.0% fail | 16.8% | 2.8% | 0.08% |
| 0.5 | 50.0% fail | 3.1% | 0.1% | 0.0001% |
| 0.7 | 30.0% fail | 0.2% | 0.0006% | ≈0 |

<br>

Even with $p = 0.5$, ten tries gives **99.9% success**.

<!--
PRESENTER NOTES:
This table shows the failure probability after N independent samples. Even a coin-flip model (p=0.5) reaches 99.9% after just 10 attempts. But raw repetition is expensive. Can we do better? Yes — and the answer has existed since the 1960s.
-->

---

# But brute force is not enough

**Problem 1**: $4\times$ samples only $= 2\times$ noise reduction
$$\text{Std. Dev.} = \frac{\sigma}{\sqrt{N}}$$

**Problem 2**: What if the correct answer is **infinitely precise**?

```json
{ "api": "POST", "path": "/v2/users",
  "body": {"name": "...", "role": "admin", "org_id": 42} }
```

The probability of randomly generating **exactly** this = ?

<!--
PRESENTER NOTES:
Two problems with brute force. First, convergence is slow — only square-root. Second, and this is the killer: some tasks require exact outputs. The probability of randomly generating a specific JSON structure with exact values is essentially zero. No amount of repetition helps when the target has zero measure.
-->

---

# What if the target has **zero area**?

<br>

Imagine throwing darts at an infinite dartboard,
trying to hit a single point.

<br>

$$\mu(\text{target}) = 0 \implies P(\text{hit}) = 0$$

**No matter how many darts you throw.**

<br>

This is not a convergence problem.
This is a **measure-theoretic impossibility**.

<!--
PRESENTER NOTES:
This is the key insight. When the correct answer occupies zero measure in the output space, random sampling CANNOT find it. Not slowly — never. This is exactly the "point light" problem in computer graphics. And graphics solved it decades ago.
-->

---

<!-- _class: lead -->

# This problem was solved
# **60 years ago.**

<!--
PRESENTER NOTES:
The rendering community encountered this exact problem with point light sources in the 1960s. They developed a comprehensive toolkit of algorithms to handle it. Let me show you.
-->

---

# A path-traced image

![bg right:60% fit](https://upload.wikimedia.org/wikipedia/commons/e/ec/Glasses_800_edit.png)

Every pixel is the result of
**thousands of random samples**.

Yet the final image is
**photorealistic**.

How?

<!--
PRESENTER NOTES:
Look at this image. Every pixel you see was computed by shooting random rays into the scene. Each individual ray is noisy and unreliable. But the final image converges to ground truth. The rendering community didn't eliminate randomness — they engineered it. That's what we're going to do with LLMs.
-->

---

# "Every pixel is a gamble. But the image is certain."

<br>

The secret: **variance reduction techniques**

- Importance Sampling
- Next Event Estimation (NEE)
- Multiple Importance Sampling (MIS)
- Russian Roulette
- Metropolis Light Transport (MLT)

Each one is **provably optimal** under specific conditions.

<!--
PRESENTER NOTES:
The rendering community developed a rich taxonomy of variance reduction techniques over 60 years. Each one addresses a specific failure mode of naive random sampling. I'm going to show you that every single one of these maps directly onto an LLM agent optimization.
-->

---

<!-- _class: lead -->

# Act II
# Path Tracing 101

*For the non-graphics folks*

<!--
PRESENTER NOTES:
Before we get to the analogy, let me give you a quick crash course on how path tracing actually works. I promise to keep it visual and intuitive.
-->

---

# How light works (simplified)

```
    💡 Light Source
     |
     | photon
     v
   ┌─────┐  reflect   ┌─────┐  reflect   👁️ Camera
   │wall │ ────────→ │floor│ ────────→
   └─────┘            └─────┘
```

Light leaves a source → bounces off surfaces → reaches your eye.

Each bounce changes the light's color/intensity (BRDF).

<!--
PRESENTER NOTES:
In the real world, light leaves a source, bounces off surfaces, and eventually reaches your eye. Each surface interaction — each bounce — modifies the light according to the surface's material properties, which we call the BRDF.
-->

---

# Path tracing: reverse the process

```
   👁️ Camera
     |
     | trace ray backwards
     v
   ┌─────┐  bounce    ┌─────┐  bounce    💡 Light?
   │floor│ ────────→ │wall │ ────────→   (maybe)
   └─────┘            └─────┘
```

Shoot rays **from the camera** into the scene.
At each surface, pick a **random direction** and keep going.
If you eventually hit a light → that pixel gets color.
If not → black.

<!--
PRESENTER NOTES:
Path tracing works backwards. We shoot rays from the camera, bounce them randomly off surfaces, and hope they eventually find a light source. If a ray finds light, the pixel gets color. If it doesn't, the pixel stays black. This is fundamentally a random process.
-->

---

# 1 SPP → 4096 SPP

| 1 sample/pixel | 16 spp | 256 spp | 4096 spp |
|:-:|:-:|:-:|:-:|
| Pure noise | Very noisy | Getting there | Clean |
| ░░▓░▒░░▓░ | ▒▓▒▓▒▓▒▓ | ▓▓▒▓▓▓▒▓ | ████████ |

<br>

More samples → less noise → converges to ground truth.

$$\text{Error} \propto \frac{1}{\sqrt{N}}$$

**4× samples = 2× less noise** (square root convergence)

<!--
PRESENTER NOTES:
Here's what happens as you increase samples per pixel. At 1 SPP, it's pure noise. At 4096, it's clean. The convergence rate is 1/sqrt(N) — so to halve the noise, you need 4x the samples. This is too slow for production. That's why we need smarter algorithms.
-->

---

# The Rendering Equation (Kajiya 1986)

$$L_o(\mathbf{x}, \omega_o) = L_e(\mathbf{x}, \omega_o) + \int_{\Omega} f_r(\mathbf{x}, \omega_i, \omega_o) \, L_i(\mathbf{x}, \omega_i) \, (\omega_i \cdot \mathbf{n}) \, d\omega_i$$

<div class="columns">
<div>

| Symbol | Meaning |
|--------|---------|
| $L_o$ | Light leaving surface |
| $L_e$ | Self-emitted light |
| $f_r$ | Surface material (BRDF) |
| $L_i$ | Incoming light |

</div>
<div>

**Translation:**

Total light out =
Self-emission +
∫ (material × incoming light)
over all directions

</div>
</div>

<!--
PRESENTER NOTES:
This is THE fundamental equation of rendering, by Kajiya in 1986. Don't worry about the symbols — the key point is: total outgoing light equals emission plus an integral over all possible incoming light directions, weighted by the material. This integral cannot be solved analytically. We must use Monte Carlo methods.
-->

---

# Monte Carlo = Throw random darts

**Problem**: Compute $\int_0^1 f(x) \, dx$

**Solution**: Sample random points, average the results.

$$\hat{I}_N = \frac{1}{N} \sum_{i=1}^{N} f(x_i), \quad x_i \sim \text{Uniform}(0, 1)$$

**Variance**: $\text{Var}[\hat{I}_N] = \sigma^2 / N$

Like estimating a room's temperature by randomly checking $N$ spots.

<!--
PRESENTER NOTES:
Monte Carlo integration is conceptually simple: to estimate an integral, throw random darts and average the results. The more darts, the better the estimate. But convergence is slow — 1/N for variance, 1/sqrt(N) for standard deviation. So the question becomes: can we throw darts SMARTER?
-->

---

# $\text{Var} = \sigma^2 / N$ is too slow. What now?

<br>

**The graphics community's answer:**

Don't throw darts randomly.
**Throw them where they matter most.**

<br>

Six key techniques:

1. **Importance Sampling** — aim at bright spots
2. **NEE** — connect directly to lights
3. **MIS** — combine multiple strategies optimally
4. **Russian Roulette** — kill hopeless paths early
5. **MLT** — mutate good paths instead of starting over
6. Path-space MIS — combine everything

<!--
PRESENTER NOTES:
The rendering community's answer to slow convergence is: don't sample uniformly. Sample smartly. Over 60 years they developed six key techniques, each addressing a different failure mode. I'll explain each one with a visual, then show you how each maps to an LLM agent optimization.
-->

---

# Importance Sampling (IS)

**Bad**: Sample directions uniformly → most rays hit nothing

**Good**: Sample directions toward where light is likely

$$\hat{I} = \frac{1}{N} \sum_{i=1}^{N} \frac{f(x_i)}{q(x_i)}, \quad x_i \sim q$$

Optimal: $q^*(x) \propto |f(x)|$ → **zero variance**

```
  Uniform:     ·  ·  ·  ·  ·  ·  ·  ·     (wasteful)
  Importance:  · · ···· · ·                  (focused)
                   ^^^^
                bright area
```

<!--
PRESENTER NOTES:
Importance sampling says: instead of sampling uniformly, sample more where the function is large. If you could sample exactly proportional to the integrand, you'd get zero variance. In practice, we approximate. This is like aiming your darts at the bullseye instead of throwing blindly.
-->

---

# Next Event Estimation (NEE)

**Problem**: Random rays almost never find small lights.

**Solution**: At every surface point, **explicitly connect** to the light.

```
        💡 Light
       ╱ ↑
      ╱  shadow ray (explicit connection)
     ╱
   ┌─────┐          (don't wait for random bounce
   │point│           to find the light — CONNECT!)
   └─────┘
```

Used by **99%+** of production renderers.

<!--
PRESENTER NOTES:
NEE is critical. Instead of hoping a random bounce direction happens to point at the light, we explicitly shoot a ray toward the light at every surface interaction. This is especially important for small lights — and absolutely essential for point lights, which have zero area.
-->

---

# The Point Light Problem

A point light has **zero area**.

$$\mu(\{\omega : \omega \text{ hits point light}\}) = 0$$

The probability of a random ray hitting it: **exactly 0**.

Not "very small" — mathematically **zero**.

```
Random rays:  →  →  →  →  →  →  →  →  →
                                            💡 (missed!)
NEE:          ────────────────────────────→ 💡 (found!)
```

**NEE is not an optimization. It is a necessity.**

<!--
PRESENTER NOTES:
THIS is the key slide. A point light has zero solid angle. No random ray will ever find it. Not in a million samples. NEE solves this by explicitly connecting to the light. Without NEE, scenes with point lights render as pure black. This has a profound analogy in the agent world, which I'll show you shortly.
-->

---

# MIS: Combine strategies optimally

**Situation**: BSDF sampling is good for glossy surfaces.
Light sampling is good for small lights.
Neither is good for all cases.

**MIS** (Veach 1995): Combine both with optimal weights.

$$w_i(x) = \frac{n_i \, p_i(x)}{\sum_k n_k \, p_k(x)}$$

Automatically gives credit to the **best strategy per sample**.

<!--
PRESENTER NOTES:
MIS is Veach's brilliant contribution. Instead of choosing one sampling strategy, combine multiple strategies and weight each sample by how well-suited its strategy was. The balance heuristic weight automatically favors the strategy that was best for that particular sample. This is provably near-optimal.
-->

---

# Russian Roulette: Kill hopeless paths

After many bounces, a path carries very little energy.

$$\hat{L} = \begin{cases} L / q & \text{with prob } q \\ 0 & \text{with prob } 1-q \end{cases}$$

**Unbiased**: $E[\hat{L}] = q \cdot L/q + (1-q) \cdot 0 = L$ ✓

Saves compute on paths that won't contribute much.
Upweights survivors to maintain correctness.

<!--
PRESENTER NOTES:
Russian Roulette is elegant. When a path is carrying very little energy, we probabilistically terminate it. But we upweight the surviving paths by 1/q to compensate. This is provably unbiased — it doesn't introduce any systematic error, just variance. And the variance increase is small for paths that were nearly worthless anyway.
-->

---

# MLT: Mutate good paths

Found a good path? **Don't start over.** Perturb it slightly.

$$\alpha = \min\!\left(1, \frac{F(\bar{p}')}{F(\bar{p})}\right)$$

Accept if better. Reject if worse. *Metropolis-Hastings.*

```
Good path:     A → B → C → D → E     (score: 0.85)
Mutation:      A → B → C'→ D → E     (score: 0.91) ✓ Accept!
Mutation:      A → B'→ C → D → E     (score: 0.62) ✗ Reject.
```

<!--
PRESENTER NOTES:
MLT is inspired by Metropolis-Hastings MCMC. Once you find a good rendering path, instead of starting from scratch, you make small changes to it. If the change improves the result, accept it. If not, reject it and keep the old path. This is incredibly efficient for exploring the neighborhood of good solutions.
-->

---

<!-- _class: lead -->

# Act III
# What If LLM = Path Tracer?

*The mapping that changes everything*

<!--
PRESENTER NOTES:
Now we get to the core insight. Every single technique I just showed you has a direct counterpart in the world of LLM agents. Let me show you the mapping.
-->

---

# Light path vs Agent path

<div class="columns">
<div>

**Path Tracing**

```
Camera
  → Surface₁ (bounce)
    → Surface₂ (bounce)
      → Surface₃ (bounce)
        → Light ✓
```

Each bounce = random direction
Throughput = $\prod f_r \cdot \cos\theta$

</div>
<div>

**Agent Workflow**

```
Task
  → Step₁ (LLM call)
    → Step₂ (LLM call)
      → Step₃ (LLM call)
        → Result ✓
```

Each step = random action
Quality = $\prod T(s_k, a_k)$

</div>
</div>

**Same structure. Same math. Same optimizations.**

<!--
PRESENTER NOTES:
A rendering path is a chain of random bounces from camera to light. An agent workflow is a chain of random LLM calls from task to result. The mathematical structure is identical. Both are sequences of stochastic decisions that multiply together to produce a final value.
-->

---

# Rendering Equation → Agent Quality Equation

$$L_o = L_e + \int_{\Omega} \underbrace{f_r}_{\text{BRDF}} \cdot L_i \cdot \underbrace{(\omega \cdot \mathbf{n})}_{\text{cosine}} \, d\omega$$

$$\Huge\Downarrow$$

$$Q(s_k) = Q_{\text{direct}} + \int_{\mathcal{A}} \underbrace{T(s_k, a)}_{\text{transfer}} \cdot Q(s_{k+1}) \cdot \underbrace{p(a|s_k)}_{\text{LLM prob}} \, da$$

**Same Fredholm integral equation of the second kind.**

<!--
PRESENTER NOTES:
The rendering equation and our Agent Quality Equation are BOTH Fredholm integral equations of the second kind. The BRDF maps to the transfer function. The cosine-weighted solid angle measure maps to the LLM's probability distribution. The recursive structure is identical. This means every algorithm that works for one MUST work for the other.
-->

---

# Veach Path Integral → Agent Path Integral

**Rendering** (Veach 1997):
$$I = \int_{\bar{\Omega}} f(\bar{x}) \, d\mu(\bar{x})$$

**Agent**:
$$\mathcal{Q} = \int_{\bar{\mathcal{P}}} F(\bar{p}) \, d\nu(\bar{p})$$

where $\bar{p} = (s_0, a_0, s_1, a_1, \ldots, s_K)$

$F(\bar{p}) = Q_{\text{final}} \cdot \prod_{k} T(s_k, a_k)$

**Integration over the space of all possible paths.**

<!--
PRESENTER NOTES:
At the path integral level, the mapping is even cleaner. Both are integrals over a space of paths. The measurement contribution function maps to the path quality function. The path-space measure maps to the product of LLM probabilities. This is not a metaphor — it's a mathematical isomorphism.
-->

---

# The Complete Mapping

| Path Tracing | Agent Workflow |
|:--|:--|
| Ray | Single LLM call |
| Path $(x_0 \to \ldots \to x_K)$ | Execution chain $(s_0 \to \ldots \to s_K)$ |
| Radiance $L$ | Quality score $Q$ |
| BRDF $f_r$ | Transfer function $T(s,a)$ |
| SPP (samples/pixel) | Samples per task |
| Point light ($\mu = 0$) | Exact-answer task |
| NEE | RAG + tool calls |
| BSDF sampling | Free LLM generation |
| MIS | Multi-strategy fusion |
| Russian Roulette | Validator-based pruning |
| MLT | Iterative refinement |
| BVH | Vector database |

<!--
PRESENTER NOTES:
Here's the complete mapping table. I want to draw your attention to a few key entries. The point light maps to exact-answer tasks. NEE maps to RAG and tool calls. This isn't just a loose analogy — each mapping is backed by the same mathematical structure.
-->

---

# BRDF = Transfer Function

<div class="columns">
<div>

**Rendering BRDF**

How a surface transforms light:
- Mirror: passes light perfectly
- Diffuse: scatters everywhere
- Glass: splits into reflect + refract

$f_r(\omega_i, \omega_o) \in [0, 1]$

</div>
<div>

**Agent Transfer**

How a step transforms quality:
- Good step: preserves quality
- Bad step: degrades quality
- Hallucination: destroys quality

$T(s_k, a) \in [0, 1]$

</div>
</div>

Energy conservation: $\int f_r \leq 1$ vs Quality bound: $T \leq 1$

<!--
PRESENTER NOTES:
The BRDF tells you how a surface transforms incoming light. A mirror passes it perfectly. A rough surface scatters it. The transfer function tells you how an agent step transforms quality. A good step preserves it. A bad step degrades it. The mathematical structure is the same.
-->

---

# SPP = Samples Per Task

<div class="columns">
<div>

**Rendering**

```
Pixel (200, 300):
  Ray 1: L = 0.3
  Ray 2: L = 0.8
  Ray 3: L = 0.5
  Ray 4: L = 0.7
  ─────────────
  Average: 0.575
```

</div>
<div>

**Agent**

```
Task "Generate color palette":
  Call 1: Score = 0.4
  Call 2: Score = 0.9
  Call 3: Score = 0.6
  Call 4: Score = 0.8
  ─────────────────
  Best-of-4: 0.9
```

</div>
</div>

More samples → better result. Same $O(1/\sqrt{N})$ convergence.

<!--
PRESENTER NOTES:
In rendering, we shoot N rays per pixel and average. In agents, we make N calls per task and take the best. The convergence rate is the same. And the optimization techniques that speed up rendering convergence will speed up agent convergence too.
-->

---

# NEE-Agent = RAG + Tool Calls

<div class="columns">
<div>

**Rendering NEE**

Don't wait for random bounce
to find the light.

**Connect directly.**

```
Surface ──→ Light
       (explicit ray)
```

</div>
<div>

**Agent NEE**

Don't wait for random generation
to produce exact answers.

**Query directly.**

```
Agent ──→ RAG / API / Tool
      (explicit lookup)
```

</div>
</div>

$$\hat{Q}_{\text{NEE}} = Q_{\text{direct}} + \frac{T(s, a^*) \cdot Q^*}{\underbrace{p_{\text{ref}}(a^*)}_{\text{RAG PDF}}} \cdot \underbrace{\mathbb{1}[\text{valid}]}_{\text{shadow ray}}$$

<!--
PRESENTER NOTES:
NEE in rendering explicitly connects each surface point to the light. Agent NEE explicitly connects each agent step to a reference knowledge source — RAG, an API, or a verified tool. The shadow ray becomes a validity check. This isn't just a metaphor: the math is identical.
-->

---

# Agent NEE: explicit connection to truth

```
Step 1: "Generate worldview"
  │
  │ (LLM freely generates — BSDF sampling)
  │
Step 2: "Generate color palette"
  │
  ├──→ LLM generates freely           (random bounce)
  │
  └──→ RAG retrieves reference         (NEE ← connects to light)
       palettes from past projects
  │
  ├── Validator checks compatibility   (shadow ray)
  │
  └── MIS combines both results        (balance heuristic)
```

<!--
PRESENTER NOTES:
Here's what it looks like in practice. At each step, we have two sampling strategies running in parallel: the LLM generates freely (like BSDF sampling), and RAG retrieves verified references (like NEE connecting to a light). A validator checks compatibility (shadow ray), and MIS combines both with optimal weights.
-->

---

# MIS-Agent: Three strategies in parallel

| Strategy | Rendering | Agent | Strength |
|:--|:--|:--|:--|
| $p_1$: Free gen | BSDF sampling | LLM generates | Broad coverage |
| $p_2$: Guided | Light sampling | RAG-augmented | Known-good regions |
| $p_3$: Tools | Delta (point light) | API / tool call | Exact answers |

$$w_i(a) = \frac{n_i \, p_i(a)}{\sum_k n_k \, p_k(a)}$$

**MIS automatically picks the best strategy per sample.**

<!--
PRESENTER NOTES:
Agent MIS combines three strategies: free generation, RAG-guided generation, and tool calls. The balance heuristic weight automatically assigns credit to whichever strategy was best for each sample. For creative tasks, free generation dominates. For precise tasks, tool calls dominate. MIS handles everything.
-->

---

# Balance Heuristic: automatic weight assignment

```
Task: "What's 7 × 8?"

  Free gen (p₁):    "56"   → p₁("56") = 0.7   w₁ = 0.26
  RAG (p₂):         "56"   → p₂("56") = 0.3   w₂ = 0.11
  Calculator (p₃):  "56"   → p₃("56") = 1.0   w₃ = 0.63  ← dominates!
```

```
Task: "Describe a cyberpunk sunset"

  Free gen (p₁):    "The neon..." → p₁ = 0.8   w₁ = 0.67  ← dominates!
  RAG (p₂):         "Reference.." → p₂ = 0.3   w₂ = 0.25
  Tool (p₃):        N/A           → p₃ ≈ 0     w₃ ≈ 0
```

<!--
PRESENTER NOTES:
Here's MIS in action. For a math question, the calculator (tool call) dominates — it's the point light direct sampling. For a creative writing task, free generation dominates — it's like BSDF sampling on a diffuse surface. MIS handles BOTH cases optimally without any manual switching.
-->

---

# Russian Roulette Agent: Validator decides fate

```
Step 1: Worldview ──→ Score: 0.85 ──→ Continue (q = 1.0)
Step 2: Palette   ──→ Score: 0.72 ──→ Continue (q = 1.0)
Step 3: Materials ──→ Score: 0.25 ──→ TERMINATE (q = 0.36) 🎲
                                      ↑
                                 Too low quality.
                                 Don't waste tokens
                                 on Steps 4 & 5.
```

$$q_k = \min\!\left(\frac{Q_k}{Q_{\text{threshold}}}, 1\right)$$

Saves tokens. **Provably unbiased.**

<!--
PRESENTER NOTES:
Russian Roulette in agents works like this: after each step, a validator scores the partial result. If the score is low, we probabilistically terminate the path — don't waste tokens continuing a doomed chain. Surviving paths are upweighted by 1/q to maintain unbiasedness. This is exactly how path tracers handle low-energy paths.
-->

---

# Importance Sampling Agent: Constraint Buffer

**Extract "visual anchors" from prior steps → guide next step.**

```
Step 1 output: "Post-apocalyptic world with bioluminescent flora"
                                    ↓
         Constraint Buffer: {apocalyptic, bioluminescent, flora}
                                    ↓
Step 2 prompt: "Generate color palette.
               CONSTRAINTS: apocalyptic, bioluminescent, flora"
```

$$p_{\text{guided}}(a | s) \propto p_{\text{LLM}}(a | s) \cdot \prod_j \phi(a, c_j)$$

Focuses sampling on **high-quality regions**.

<!--
PRESENTER NOTES:
Importance sampling for agents works through a Constraint Buffer. We extract key visual anchors from prior steps and inject them as constraints for the next step. This biases the LLM's output distribution toward high-quality regions — exactly like importance sampling biases ray directions toward bright areas.
-->

---

# MLT-Agent: Mutate, don't regenerate

```
Draft v1:  [World] [Palette] [Materials] [Chars] [Envs]  Score: 0.72
                       ↓ mutate only Palette
Draft v2:  [World] [Palette'] [Materials] [Chars] [Envs]  Score: 0.78 ✓
                                    ↓ mutate only Materials
Draft v3:  [World] [Palette'] [Materials'] [Chars] [Envs]  Score: 0.81 ✓
                                              ↓ mutate only Chars
Draft v4:  [World] [Palette'] [Materials'] [Chars'] [Envs]  Score: 0.75 ✗
           (reject — keep v3)
```

Converges to $\pi(\bar{p}) \propto F(\bar{p})$ — spends time in high-quality space.

<!--
PRESENTER NOTES:
Agent MLT starts with a complete initial draft, then mutates one section at a time. If the mutation improves global quality, accept it. If not, reject and keep the previous version. This Markov chain converges to a distribution proportional to quality — meaning it naturally gravitates toward good documents.
-->

---

# The Full "AI Rendering Pipeline"

```
┌─────────────────────────────────────────────────────┐
│                  Input: Task Description              │
└──────────────────────┬──────────────────────────────┘
                       ↓
   ┌────────────┬──────┴──────┬────────────┐
   │ Strategy 1 │ Strategy 2  │ Strategy 3 │   ← MIS
   │ Free Gen   │ RAG/NEE     │ Tool Call  │
   └─────┬──────┴──────┬──────┴──────┬─────┘
         ↓             ↓             ↓
   ┌─────┴─────────────┴─────────────┴─────┐
   │         Validator (Shadow Ray)         │   ← RR
   └─────────────────┬─────────────────────┘
                     ↓
   ┌─────────────────┴─────────────────────┐
   │    Constraint Buffer (IS guidance)     │   ← IS
   └─────────────────┬─────────────────────┘
                     ↓
   ┌─────────────────┴─────────────────────┐
   │    MLT Refinement Loop                 │   ← MLT
   └─────────────────┬─────────────────────┘
                     ↓
              Final Output
```

<!--
PRESENTER NOTES:
Here's the full pipeline. MIS combines three strategies at each step. A validator acts as the shadow ray, gating contributions. The Constraint Buffer provides importance sampling guidance. And MLT refines the final result through iterative mutation. Every component has a direct counterpart in production path tracers.
-->

---

# The Task Reflectance Spectrum

| BRDF | $\mu(\mathcal{A}^*)$ | Task Example | Best Strategy |
|:--|:--|:--|:--|
| Diffuse | Large | "Write a poem" | Free generation |
| Glossy | Small | "Write Art Bible" | IS + MIS |
| Specular | Point | "$\int_0^1 x^2 dx$?" | Direct computation |
| Point light | **Zero** | "Exact API call" | NEE (tools) |

<br>

**MIS handles the entire spectrum without manual switching.**

<!--
PRESENTER NOTES:
Real tasks exist on a spectrum from "diffuse" (many valid outputs) to "point light" (one exact answer). MIS automatically allocates sampling budget across this spectrum. For diffuse tasks, free generation is enough. For point light tasks, you MUST use tools. MIS handles everything in between.
-->

---

# Existing methods in our framework

| Method | In Our Framework |
|:--|:--|
| Best-of-N | Basic Monte Carlo |
| Self-Consistency | MC + majority voting |
| Tree-of-Thought | MCTS in path space |
| **RAG** | **NEE (light source connection)** |
| **Tool use** | **Point light sampling (delta dist.)** |
| Fork-Merge | Parallel paths + MIS |
| Sherlock verification | Russian Roulette |

**All are special cases of MC variance reduction.**

<!--
PRESENTER NOTES:
This is the unifying power of our framework. Every existing technique — Best-of-N, self-consistency, RAG, tool use — is a special case of a known Monte Carlo variance reduction technique. We're not inventing new methods. We're recognizing that the methods already exist and providing a unified theoretical framework.
-->

---

<!-- _class: lead -->

# Act IV
# The Point Light Theorem

*The sharpest result in this framework*

<!--
PRESENTER NOTES:
Now I want to show you what I think is the most important theoretical result in this framework. It explains WHY certain agent optimizations are not just nice to have — they're mathematically necessary.
-->

---

# Point Light = Zero-Measure Correct Answer

**In rendering:**

A point light has zero solid angle.
$P(\text{random ray hits it}) = 0$.

**In agents:**

Some tasks have correct answers with zero measure.
$P(\text{random generation is correct}) = 0$.

Examples:
- Exact JSON schema: `{"name": "str", "age": "int", "id": 42}`
- Precise API call with correct parameters
- Code that compiles AND passes all tests

<!--
PRESENTER NOTES:
The point light theorem formalizes something practitioners already know intuitively: some tasks are impossible to solve by random generation alone. The correct answer is a single point in an infinite output space. No amount of random sampling will ever find it.
-->

---

# Definition: Agent Point Light

<br>

A task has the **point light property** if:

$$\mu(\mathcal{A}^*) = 0$$

where $\mathcal{A}^*$ is the set of correct outputs
and $\mu$ is the measure induced by $p_{\text{LLM}}(\cdot | s)$.

<br>

**Practical version**: $\epsilon$-point-light when $\mu(\mathcal{A}^*) < \epsilon \ll 1$

<!--
PRESENTER NOTES:
Formally, a task is a "point light" when the set of correct outputs has zero measure under the LLM's output distribution. In practice, we use the epsilon version — the correct outputs have negligibly small probability.
-->

---

# Theorem 1: Pure Sampling Unreachability

<br>

**Theorem.** For a point-light task ($\mu(\mathcal{A}^*) = 0$):

$$P\!\left(\exists\, i \leq N : a_i \in \mathcal{A}^*\right) = 0 \quad \forall\, N \in \mathbb{N}$$

<br>

**Proof.** $P(a_i \in \mathcal{A}^*) = \mu(\mathcal{A}^*) = 0$ for each $i$.
By subadditivity: $P(\bigcup_i \{a_i \in \mathcal{A}^*\}) \leq \sum_i 0 = 0.$ $\square$

<br>

**No matter how many times you sample, you will never find it.**

<!--
PRESENTER NOTES:
This theorem says: if the correct answer has zero measure, then NO amount of random sampling will ever find it. Not "probably won't" — NEVER. The proof is one line of measure theory. This is the mathematical formalization of why raw LLM generation fails on precision tasks.
-->

---

# Theorem 2: NEE Reachability

<br>

**Theorem.** If $\exists\, p_{\text{ref}}$ with $p_{\text{ref}}(\mathcal{A}^*) > 0$, then:

$$E[\hat{Q}_{\text{NEE}}] > 0 \quad \text{and} \quad \text{Var}[\hat{Q}_{\text{NEE}}] < \infty$$

<br>

**NEE (RAG / tool calls) makes the impossible possible.**

The reference distribution $p_{\text{ref}}$ assigns positive probability
to the correct answer set → success becomes achievable.

<!--
PRESENTER NOTES:
Theorem 2 is the positive counterpart. If you have a reference distribution — a RAG knowledge base, a tool, an API — that assigns positive probability to the correct answer, then NEE succeeds where pure sampling fails. The expected quality becomes positive and the variance is finite.
-->

---

# Corollary: NEE is **necessary**, not optional

<br>

> For tasks with $\mu(\mathcal{A}^*) = 0$:
>
> RAG and tool calls are not optimizations.
> They are **necessary conditions** for non-zero expected quality.

<br>

**This is why function calling works.**
**This is why RAG matters.**
**This is the mathematical reason.**

<!--
PRESENTER NOTES:
This is the punchline. For point-light tasks, RAG and tool calls are not "nice to have" optimizations. They are mathematically necessary. Without them, the expected quality is zero, no matter how many tokens you spend. This provides the first theoretical justification for why function calling and RAG are essential parts of modern agent architectures.
-->

---

# The Spectrum: Diffuse → Point Light

```
Diffuse          Glossy          Specular        Point Light
"Write a poem"   "Art Bible"     "∫x²dx = ?"    "POST /api/v2"
                                  
██████████████   ████░░░░░░░░░   █░░░░░░░░░░░░   ·
 many valid       some valid      one answer      exact format
 answers          answers                         zero measure

Free gen works   IS helps        Need guidance    MUST use NEE
                                                  (tools/RAG)
```

**MIS automatically handles the entire spectrum.**

<!--
PRESENTER NOTES:
Real-world tasks span this entire spectrum. Creative tasks are diffuse — many valid outputs. Style guides are glossy — a range of acceptable outputs. Math is specular — one answer. API calls are point lights — exact format required. The beauty of MIS is that it handles all of these automatically.
-->

---

# MIS: one pipeline for all task types

**For diffuse tasks** ($p_1$ dominates):
$w_{\text{free}} \to 1, \; w_{\text{RAG}} \to 0, \; w_{\text{tool}} \to 0$

**For point-light tasks** ($p_3$ dominates):
$w_{\text{free}} \to 0, \; w_{\text{RAG}} \to 0, \; w_{\text{tool}} \to 1$

**For mixed tasks** (MIS balances):
$w_{\text{free}} \approx 0.4, \; w_{\text{RAG}} \approx 0.4, \; w_{\text{tool}} \approx 0.2$

No manual tuning. The math handles it.

<!--
PRESENTER NOTES:
This is the practical power of MIS. You don't need to classify tasks manually. You don't need to decide when to use RAG vs free generation. The balance heuristic weights automatically shift to favor whatever strategy works best for each specific sample. One pipeline handles everything.
-->

---

<!-- _class: lead -->

# Act V
# Winning with Cheap Models

*The Sampling Efficiency Criterion*

<!--
PRESENTER NOTES:
Now let's talk about cost. If we're going to sample multiple times, maybe we can use cheaper models and still win. Let me show you the math that makes this precise.
-->

---

# The Sampling Efficiency

Model $M$: accuracy $p_M$, cost per call $C_M$

Under budget $B$: can make $N = B / C_M$ calls.

$$P_{\text{success}} = 1 - (1-p_M)^{B/C_M}$$

<br>

$$\boxed{\eta_M = \frac{-\ln(1 - p_M)}{C_M} \approx \frac{p_M}{C_M}}$$

<br>

**Higher $\eta$ = better model at any budget.**

<!--
PRESENTER NOTES:
The sampling efficiency eta is the key metric. It measures how much "failure reduction" you get per dollar. A model with higher eta is always preferred, regardless of its individual accuracy. When p is small, eta simplifies to p/C — accuracy per dollar.
-->

---

# Small × Many vs Large × Few

| Model | $p_M$ | $C_M$ | $\eta_M$ |
|:--|:--|:--|:--|
| GPT-4o-mini | 0.30 | $0.003 | **119** |
| Claude Haiku | 0.35 | $0.004 | **108** |
| GPT-4o | 0.75 | $0.06 | **23** |
| Claude Sonnet | 0.80 | $0.09 | **18** |

<br>

At **$1 budget**: mini gets 333 tries → $P = 1-(0.7)^{333} \approx 1$
GPT-4o gets 16 tries → $P = 1-(0.25)^{16} \approx 1$

But mini is **5× cheaper per unit of reliability gained**.

<!--
PRESENTER NOTES:
Look at the eta values. GPT-4o-mini has eta of 119 while GPT-4o has only 23. That means per dollar spent, mini is 5x more efficient at reducing failure probability. This formalizes the "Large Language Monkeys" finding that small models with repeated sampling outperform large models.
-->

---

# "Large Language Monkeys" (2024) — confirmed

**Empirical finding**: DeepSeek on SWE-bench:
- 1 sample: 15.9% solved
- 250 samples: **56% solved**

5 DeepSeek samples > 1 GPT-4o sample.
Not because DeepSeek is smarter.
Because $\eta_{\text{DeepSeek}} > \eta_{\text{GPT-4o}}$.

**Our framework provides the theoretical explanation.**

<!--
PRESENTER NOTES:
The Large Language Monkeys paper showed empirically that small models with many samples beat large models with few samples. Our framework explains WHY: the sampling efficiency eta of smaller, cheaper models is often higher than that of expensive models. This isn't a fluke — it's a mathematical consequence.
-->

---

# When does the small model win?

$$\eta_{\text{small}} > \eta_{\text{large}}$$
$$\frac{p_s}{C_s} > \frac{p_l}{C_l}$$

**Small model wins when:**
$$\frac{p_s}{p_l} > \frac{C_s}{C_l}$$

If Haiku is 2× worse but 20× cheaper → Haiku wins.
If mini is 3× worse but 20× cheaper → mini wins.

The ratio matters, not the absolute accuracy.

<!--
PRESENTER NOTES:
The crossover condition is simple: the small model wins when its accuracy ratio exceeds its cost ratio. If mini is only half as accurate but twenty times cheaper, mini wins by a large margin. This gives us a precise decision criterion for model selection.
-->

---

# Real cost calculation

**Task**: Generate Art Bible section
**Budget**: $5

| Approach | Model | Calls | $P_{\text{success}}$ | Actual Cost |
|:--|:--|--:|:--|--:|
| Single shot | Sonnet | 1 | 80% | $0.09 |
| 5 shots | Sonnet | 5 | 99.97% | $0.45 |
| 50 shots | mini | 50 | 99.9999% | $0.15 |
| 200 shots | mini | 200 | ≈ 100% | $0.60 |

<br>

**mini × 50 > Sonnet × 5** at **1/3 the cost**.

<!--
PRESENTER NOTES:
Here's a concrete calculation. For a $5 budget, 50 shots with mini achieves higher reliability than 5 shots with Sonnet at one-third the cost. The remaining budget can be used for MORE tasks or MORE sophisticated pipeline components like validators and MLT refinement.
-->

---

<!-- _class: lead -->

# Act VI
# How We'll Prove It

*Experimental Design + Demo Preview*

<!--
PRESENTER NOTES:
Theory is nice, but we need empirical validation. Let me walk you through our experimental plan and show you the visualization dashboard we're building.
-->

---

# Experiment 0: Point Light Validation

**Can pure sampling find exact answers? (Spoiler: No.)**

```
Task: Generate exact JSON matching strict schema

Pure sampling:    N=1     N=10    N=100   N=1000
                  0%      0%      2%      3%      ← plateaus!

NEE (tool call):  N=1     N=10
                  95%     99.8%              ← immediately high

MIS (mix):        N=1     N=10
                  72%     99.5%              ← combines best of both
```

<!--
PRESENTER NOTES:
Experiment 0 is the most dramatic. We give the model a strict JSON schema task and measure exact match rate. Pure sampling should plateau near zero regardless of N. NEE should achieve high accuracy immediately. MIS should match NEE on point-light tasks and outperform it on mixed tasks.
-->

---

# Experiments 1-2: Basic MC + Russian Roulette

**Exp 1**: Validate $O(1/\sqrt{N})$ convergence on Art Bible sections.
$N \in \{1, 4, 16, 64, 256\}$ across small vs large models.

**Exp 2**: 5-step Art Bible chain with RR.

```
Without RR:  Step1 → Step2 → Step3 → Step4 → Step5
             100%    100%    100%    100%    100% of paths

With RR:     Step1 → Step2 → Step3 ✗ (terminated 40%)
             100%    100%    60%     60%    60% of paths
             
             Token savings: ~30%
             Quality: no degradation (unbiased!)
```

<!--
PRESENTER NOTES:
Experiment 1 validates basic convergence. Experiment 2 tests Russian Roulette — we expect about 30% token savings with no quality degradation because RR is provably unbiased. The terminated paths were the ones that would have failed anyway.
-->

---

# Experiments 3-4: IS + MLT

**Exp 3**: Constraint Buffer reduces variance.

```
Unconstrained:  σ² = 0.15   (30 samples to converge)
Constrained:    σ² = 0.04   (8 samples to converge)
                             3.75× speedup
```

**Exp 4**: MLT vs regeneration.

```
Regenerate ×10:  Score = 0.78 (best of 10 fresh attempts)
MLT 1 + 9 mut:  Score = 0.86 (initial + 9 local mutations)
                              +10% quality at same cost
```

<!--
PRESENTER NOTES:
Experiment 3 tests whether the Constraint Buffer (importance sampling) reduces variance. We expect about 4x faster convergence. Experiment 4 tests MLT: starting with one draft and mutating 9 times should outperform generating 10 fresh drafts, because mutations preserve the good parts.
-->

---

# Experiments 5-6: MIS + Cost Analysis

**Exp 5**: MIS outperforms any single strategy.

| Method | Art Bible Quality |
|:--|:--|
| Free only (N=30) | 0.71 |
| RAG only (N=30) | 0.74 |
| Tool only (N=30) | 0.68 |
| **MIS (10+10+10)** | **0.83** |

**Exp 6**: Fixed budget → measure empirical $\eta_M$.

<!--
PRESENTER NOTES:
Experiment 5 is the MIS showdown. We expect the MIS combination to outperform any single strategy because different parts of the Art Bible benefit from different strategies. Experiment 6 measures empirical sampling efficiency to validate our theoretical criterion.
-->

---

# Visualization Dashboard (Preview)

```
┌────────────────┬───────────────────────────┐
│   Path Tree    │   Art Bible Preview       │
│    (D3.js)     │   (Live Markdown)         │
│   ┌─○          │                           │
│   ├─●─○        │   ## Color Palette        │
│   │ └─●─✗      │   Primary: Deep Crimson   │
│   └─●─○─●      │   Secondary: Midnight...  │
│     └─✗        │   ...generating...        │
├────────────────┴───────────────────────────┤
│        Quality Convergence + Cost Graph     │
│   ▐▐▐▐▌▌▌▌▌████████████████████████████   │
│   0────────────────────────────────── N     │
└─────────────────────────────────────────────┘
```

Real-time. Every path visible. Every decision traced.

<!--
PRESENTER NOTES:
We're building a web dashboard that visualizes the entire process in real-time. The left panel shows the path tree — every agent execution path, color-coded by status. The right panel shows the Art Bible being generated live. The bottom panel shows quality convergence and cost graphs. Think of it as a framebuffer for agent workflows.
-->

---

# Dashboard: Path Tree + Agent DAG

**Path Tree** (D3.js):
- 🟢 Green = accepted path
- 🔴 Red = terminated (Russian Roulette)
- ⚪ Gray = in progress

**Agent DAG** (react-flow):
```
[Worldview] → [Palette] → [Materials] → [Characters] → [Environments]
    ↕ ×N         ↕ ×N         ↕ ×N          ↕ ×N           ↕ ×N
  samples      samples      samples       samples        samples
```

Each node expandable to show parallel samples.

<!--
PRESENTER NOTES:
The path tree shows the exploration history — which paths were tried, which were accepted, which were pruned. The agent DAG shows the pipeline structure with expandable nodes. You can see how many parallel samples are running at each step, the quality scores, and the MIS weights.
-->

---

# Dashboard: Metrics + Live Preview

**Quality Convergence** (like SPP noise reduction):
```
Quality
  1.0│                              ████████
     │                    ▐▐▐▐▐████
     │           ▐▐▐▐████
     │     ▐▐████
     │▐████
  0.0└──────────────────────────────────────
     0         Samples (N)              100
```

**Token Cost** + **Strategy Weights** (pie chart):
Free: 40% | RAG: 35% | Tool: 25%

<!--
PRESENTER NOTES:
The metrics panel shows real-time quality convergence — you'll see the curve flatten as it approaches the optimum, just like watching a path-traced image clear up. The token cost tracker and strategy weight breakdown show how the MIS weights evolve during generation.
-->

---

# Tech Stack

```
┌──────────────────────────────────────────────────┐
│  Frontend:  Next.js + React + Tailwind + shadcn  │
│  Viz:       D3.js + Recharts + react-flow        │
│  Backend:   Python FastAPI                       │
│  LLMs:      OpenAI + Anthropic + Google AI       │
│  Streaming:  Server-Sent Events (SSE)            │
└──────────────────────────────────────────────────┘

Backend modules:
  engine/sampler.py    — MC engine (naive, IS, MIS)
  engine/validator.py  — Quality scoring + RR
  engine/nee.py        — RAG integration
  engine/mlt.py        — Mutation engine
  pipeline/art_bible.py — 5-step generation chain
```

<!--
PRESENTER NOTES:
Here's our tech stack. The frontend is Next.js with D3 for the path tree visualization. The backend is Python FastAPI with modular engine components — each variance reduction technique is its own module. We use SSE for real-time streaming of agent execution to the dashboard.
-->

---

# Timeline & Milestones

| Phase | Duration | Deliverable |
|:--|:--|:--|
| Phase 0 | Done ✓ | Theory + paper + slides |
| Phase 1 | 2 weeks | Basic MC + quality scorer |
| Phase 2 | 3 weeks | NEE + MIS + RR + IS + MLT |
| Phase 3 | 2 weeks | Full Art Bible pipeline |
| Phase 4 | 2 weeks | Dashboard + experiments |

**Total: ~9 weeks to full validation.**

API keys ready: Gemini, Claude, GPT ✓

<!--
PRESENTER NOTES:
Here's our timeline. We already have the theory done. Phase 1 builds the basic sampling infrastructure. Phase 2 implements all the variance reduction techniques. Phase 3 puts it all together for Art Bible generation. Phase 4 builds the dashboard and runs all experiments. Total about 9 weeks.
-->

---

<!-- _class: lead -->

# Act VII
# Key Takeaways

<!--
PRESENTER NOTES:
Let me wrap up with the three key messages I want you to take away from this presentation.
-->

---

# Reframing the problem

<br>

| Old framing | New framing |
|:--|:--|
| "LLMs are unreliable" | "LLMs have high variance" |
| "Can't trust randomness" | "Randomness is engineerable" |
| "Need better models" | "Need better algorithms" |
| "RAG is a hack" | "RAG is mathematically necessary (NEE)" |
| "More money = better AI" | "$\eta$ determines the optimal model" |

<br>

**Variance is not a bug. Variance is a parameter to optimize.**

<!--
PRESENTER NOTES:
The most important reframing: LLM unreliability is not a fundamental flaw. It's a variance problem. And variance is something we know how to optimize. The rendering community has been doing it for 60 years. We just need to apply their techniques.
-->

---

# The Rendering Equation = The Agent Quality Equation

$$L_o = L_e + \int_\Omega f_r \cdot L_i \cdot \cos\theta \, d\omega$$

$$\Huge =$$

$$Q(s) = Q_{\text{direct}} + \int_\mathcal{A} T(s,a) \cdot Q(s') \cdot p(a|s) \, da$$

<br>

Same equation. Same algorithms. Same optimizations.
**Different domains. Identical math.**

<!--
PRESENTER NOTES:
At its core, this is the message: the rendering equation and the agent quality equation are the same mathematical object. Every algorithm developed for one applies to the other. We're not inventing new math — we're transferring 60 years of proven techniques to a new domain.
-->

---

# Three takeaways

<br>

**1.** LLM unreliability = variance. Graphics has 60 years of variance reduction.

<br>

**2.** The Point Light Theorem: for exact-answer tasks, RAG/tools are not optional — they are **mathematically necessary** (NEE).

<br>

**3.** Sampling efficiency $\eta = p/C$ determines model selection. Cheap × many often beats expensive × few.

<!--
PRESENTER NOTES:
Three things to remember. One: LLM unreliability is a variance problem with known solutions. Two: the Point Light Theorem proves that RAG and tool use are necessary for certain task types — not an optimization, a necessity. Three: the sampling efficiency criterion tells us exactly when cheap models with more samples beat expensive models.
-->

---

<!-- _class: lead -->

# Thank You

<br>

**EveryStep: Path Tracing the Agentic Workflow**

<br>

Questions?

<br>

📄 Paper: `paper/main.tex`
📊 Dashboard: `dashboard/` (coming soon)
🔬 Experiments: Phase 1 starting next week

<!--
PRESENTER NOTES:
Thank you for your attention. The paper is available in the repo, and we'll be starting Phase 1 experiments next week. I'm happy to take questions — especially from anyone who sees flaws in the analogy, because that's how we'll make this framework stronger.
-->
