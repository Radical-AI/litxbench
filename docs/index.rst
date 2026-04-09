:hide-toc:

LitXBench
=========

**A Benchmark for Extracting Experiments from Scientific Literature**

.. raw:: html

   <nav class="top-nav">
     <a href="user/introduction.html"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.744 3.744 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"/></svg> Docs</a>
     <a href="/litxbench/explorer/"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm0 1a2.5 2.5 0 0 0 2.45-2h3.1a2.5 2.5 0 0 0 4.45.5h.5a.5.5 0 0 0 0-1H13.5A2.5 2.5 0 0 0 9.05 2H5.95A2.5 2.5 0 0 0 1 2.5 2.5 2.5 0 0 0 3.5 5ZM12.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM6 9.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Zm-4.5 0a2.5 2.5 0 0 0 2.45 2.5v2a.5.5 0 0 0 1 0v-2A2.5 2.5 0 0 0 7 9.5a2.5 2.5 0 0 0-2.05-2.46V5a.5.5 0 0 0-1 0v2.04A2.5 2.5 0 0 0 1.5 9.5Zm9 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Zm1.5 0a2.5 2.5 0 0 1-4.95.5H5a.5.5 0 0 1 0-1h2.05A2.5 2.5 0 0 1 12 9.5Z"/></svg> Graph Viewer</a>
     <a href="https://arxiv.org/pdf/2604.03099"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2.75 0h10.5C14.216 0 15 .784 15 1.75v12.5A1.75 1.75 0 0 1 13.25 16H2.75A1.75 1.75 0 0 1 1 14.25V1.75C1 .784 1.784 0 2.75 0ZM2.5 1.75v12.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H2.75a.25.25 0 0 0-.25.25Zm2 3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"/></svg> Paper</a>
   </nav>

.. raw:: html

   <div class="benchmark-table-wrap">
   <table class="benchmark-table">
   <caption>
     All models were evaluated on transcribed text from Mistral OCR 3, with figures excluded from prompts.
     The per-category F1 scores correspond to model performance on extracting measurement values (Meas.), process conditions (Proc.), the set of materials (Mat.), and the set of microstructure (Config). The score weight contributions are: Meas.=0.5, Proc.=0.2, Mat.=0.15, Config=0.15.
     Uncertainties are calculated using the 95% confidence interval using the Student's t-distribution.
   </caption>
   <thead>
     <tr>
       <th rowspan="2">Method</th>
       <th colspan="3">Overall</th>
       <th colspan="4">Per-Category F1 Scores</th>
       <th colspan="2">Efficiency</th>
       <th rowspan="2">Links</th>
       <th rowspan="2">LitXAlloy Version</th>
     </tr>
     <tr>
       <th data-sort="higher">Prec.</th>
       <th data-sort="higher">Rec.</th>
       <th data-sort="higher">F1</th>
       <th data-sort="higher">Meas.</th>
       <th data-sort="higher">Proc.</th>
       <th data-sort="higher">Mat.</th>
       <th data-sort="higher">Config.</th>
       <th data-sort="lower">Attempts</th>
       <th data-sort="lower">Cost (USD)</th>
     </tr>
   </thead>
   <tbody>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">Gemini CLI (3.1 Pro Preview)</a></td>
       <td>0.80</td>
       <td>0.81</td>
       <td>0.80 &plusmn; 0.04</td>
       <td>0.74</td>
       <td>0.84</td>
       <td>0.98</td>
       <td>0.68</td>
       <td>2.47</td>
       <td>6.46</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">code</a> <a href="https://drive.google.com/file/d/1RetwmS5GY1Ix_8NbH1aLTdI1ue3IpG0U/view">run</a> <a href="https://blog.google/technology/developers/introducing-gemini-cli-open-source-ai-agent/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">Claude Code (Opus 4.6)</a></td>
       <td>0.80</td>
       <td>0.77</td>
       <td>0.78 &plusmn; 0.00</td>
       <td>0.70</td>
       <td>0.88</td>
       <td>0.94</td>
       <td>0.56</td>
       <td>1.26</td>
       <td>26.11</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">code</a> <a href="https://drive.google.com/file/d/1RetwmS5GY1Ix_8NbH1aLTdI1ue3IpG0U/view">run</a> <a href="https://www.anthropic.com/news/claude-3-7-sonnet">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">Gemini 3.1 Pro Preview</a></td>
       <td>0.79</td>
       <td>0.77</td>
       <td>0.77 &plusmn; 0.03</td>
       <td>0.70</td>
       <td>0.83</td>
       <td>0.96</td>
       <td>0.60</td>
       <td>1.51</td>
       <td>4.17</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">Gemini 3 Flash Preview</a></td>
       <td>0.74</td>
       <td>0.76</td>
       <td>0.74 &plusmn; 0.05</td>
       <td>0.61</td>
       <td>0.86</td>
       <td>0.97</td>
       <td>0.52</td>
       <td>2.58</td>
       <td>1.73</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://blog.google/products/gemini/gemini-3-flash/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">Claude Opus 4.6</a></td>
       <td>0.74</td>
       <td>0.72</td>
       <td>0.72 &plusmn; 0.04</td>
       <td>0.61</td>
       <td>0.86</td>
       <td>0.91</td>
       <td>0.54</td>
       <td>1.53</td>
       <td>5.37</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://www.anthropic.com/news/claude-opus-4-6">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">GPT-5.2 High</a></td>
       <td>0.70</td>
       <td>0.77</td>
       <td>0.72 &plusmn; 0.02</td>
       <td>0.64</td>
       <td>0.85</td>
       <td>0.97</td>
       <td>0.49</td>
       <td>1.46</td>
       <td>4.99</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://openai.com/index/introducing-gpt-5-2/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">Codex (GPT-5.2 Codex High)</a></td>
       <td>0.76</td>
       <td>0.72</td>
       <td>0.72 &plusmn; 0.01</td>
       <td>0.66</td>
       <td>0.82</td>
       <td>0.95</td>
       <td>0.52</td>
       <td>1.49</td>
       <td>4.17</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot_agentic_cli.py">code</a> <a href="https://drive.google.com/file/d/1RetwmS5GY1Ix_8NbH1aLTdI1ue3IpG0U/view">run</a> <a href="https://openai.com/index/introducing-gpt-5-2-codex/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">GPT-5 Mini Medium</a></td>
       <td>0.67</td>
       <td>0.70</td>
       <td>0.67 &plusmn; 0.04</td>
       <td>0.51</td>
       <td>0.84</td>
       <td>0.94</td>
       <td>0.41</td>
       <td>2.49</td>
       <td>3.47</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://openai.com/index/introducing-gpt-5/">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">Claude Haiku 4.5</a></td>
       <td>0.64</td>
       <td>0.68</td>
       <td>0.65 &plusmn; 0.01</td>
       <td>0.50</td>
       <td>0.84</td>
       <td>0.94</td>
       <td>0.38</td>
       <td>2.21</td>
       <td>1.72</td>
       <td class="links-cell"><a href="https://github.com/Radical-AI/litxbench/blob/main/scripts/paper/benchmarks/tasks/zero_shot.py">code</a> <a href="https://drive.google.com/file/d/1hLahFPqZLsAGYkdD9Q3kYcZSGA5IoDNm/view">run</a> <a href="https://www.anthropic.com/news/claude-haiku-4-5">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
     <tr>
       <td><a href="https://github.com/hasan-sayeed/KnowMat2">KnowMat2 (GPT-5.2 High)</a></td>
       <td>0.52</td>
       <td>0.43</td>
       <td>0.43 &plusmn; 0.29</td>
       <td>0.28</td>
       <td>0.66</td>
       <td>0.66</td>
       <td>0.19</td>
       <td>&mdash;</td>
       <td>19.40</td>
       <td class="links-cell"><a href="https://github.com/curtischong/KnowMat2">code</a> <a href="https://github.com/curtischong/KnowMat2/tree/master/std_1_high/knowmat2">run</a> <a href="https://chemrxiv.org/engage/chemrxiv/article-details/6902772ea482cba122c41c14">paper</a> <a href="https://github.com/Radical-AI/litxbench/pull/1">pr</a></td>
       <td>0.1.0</td>
     </tr>
   </tbody>
   </table>
   <p style="margin-top: 1em;">Want to add your method? See the <a href="about/contributing.html#contributing-to-the-leaderboard">Contributing</a> page for details.</p>
   </div>

.. raw:: html

   <hr>
   <div class="about-section">
   <h2>About LitXBench</h2>
   <p>LitXBench is a framework for benchmarking methods that extract experiments from literature. This project also includes <strong>LitXAlloy</strong>, a dense benchmark comprising 1426 total measurements from 19 alloy papers. By representing data using code rather than CSV or JSON, LitXBench improves the benchmark's auditability and enables programmatic data validation.</p>
   <h3>Key Features</h3>
   <p>A dense experiment extraction benchmark with 1426 values across 19 alloy papers.</p>
   <ul>
     <li><strong>Code-based material representation</strong> &mdash; Extractions are expressed as executable Python code, making them more editable and auditable than JSON or plain text.</li>
     <li><strong>High editability and auditability</strong> &mdash; Because extractions are plain Python, they are easy to review, diff, and correct, making the benchmark straightforward to maintain and extend.</li>
     <li><strong>Process lineage tracking</strong> &mdash; Measurements are linked to their full synthesis history, not just composition. This prevents incorrect one-to-many mappings between compositions and properties.</li>
     <li><strong>Canonical Values</strong> &mdash; Enums are used as canonical values to disambiguate categorical terms (such as properties, phases, synthesis kinds, etc.) across papers (e.g. compressive vs tensile fracture strain).</li>
     <li><strong>Validation at construction</strong> &mdash; Code natively provides compile-time and run-time validation, warning LLMs of extraction issues.</li>
   </ul>
   <nav class="top-nav">
     <a href="user/introduction.html"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.744 3.744 0 0 1 11.006 1h4.245a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.507a2.25 2.25 0 0 0-1.591.659l-.622.621a.75.75 0 0 1-1.06 0l-.622-.621A2.25 2.25 0 0 0 5.258 13H.75a.75.75 0 0 1-.75-.75Zm7.251 10.324.004-5.073-.002-2.253A2.25 2.25 0 0 0 5.003 2.5H1.5v9h3.757a3.75 3.75 0 0 1 1.994.574ZM8.755 4.75l-.004 7.322a3.752 3.752 0 0 1 1.992-.572H14.5v-9h-3.495a2.25 2.25 0 0 0-2.25 2.25Z"/></svg> Docs</a>
     <a href="/litxbench/explorer/"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm0 1a2.5 2.5 0 0 0 2.45-2h3.1a2.5 2.5 0 0 0 4.45.5h.5a.5.5 0 0 0 0-1H13.5A2.5 2.5 0 0 0 9.05 2H5.95A2.5 2.5 0 0 0 1 2.5 2.5 2.5 0 0 0 3.5 5ZM12.5 4a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM6 9.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Zm-4.5 0a2.5 2.5 0 0 0 2.45 2.5v2a.5.5 0 0 0 1 0v-2A2.5 2.5 0 0 0 7 9.5a2.5 2.5 0 0 0-2.05-2.46V5a.5.5 0 0 0-1 0v2.04A2.5 2.5 0 0 0 1.5 9.5Zm9 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Zm1.5 0a2.5 2.5 0 0 1-4.95.5H5a.5.5 0 0 1 0-1h2.05A2.5 2.5 0 0 1 12 9.5Z"/></svg> Graph Viewer</a>
     <a href="https://arxiv.org/pdf/2604.03099"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2.75 0h10.5C14.216 0 15 .784 15 1.75v12.5A1.75 1.75 0 0 1 13.25 16H2.75A1.75 1.75 0 0 1 1 14.25V1.75C1 .784 1.784 0 2.75 0ZM2.5 1.75v12.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25V1.75a.25.25 0 0 0-.25-.25H2.75a.25.25 0 0 0-.25.25Zm2 3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h5.5a.75.75 0 0 1 0 1.5h-5.5a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"/></svg> Paper</a>
   </nav>
   <h3>Citation</h3>
   <p>If you use LitXBench in your research, please cite:</p>
   <pre><code>@article{chong2026litxbench,
     title={LitXBench: A Benchmark for Extracting Experiments from Scientific Literature},
     author={Chong, Curtis and Colindres, Jorge},
     year={2026},
   }</code></pre>
   </div>

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: User Guide

   user/introduction
   user/core_concepts
   user/building_extractions
   user/evaluation
   user/dataset

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: About

   about/contributing
   about/license
