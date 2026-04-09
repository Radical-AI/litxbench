export interface ProcessEventInfo {
  kind: string;
  description?: string | null;
  temperature?: string | null;
  duration?: string | null;
  equipment?: string | null;
  source?: string | null;
  inputs?: string[];
}

export interface ProcessStep {
  base_name: string;
  variables: Record<string, string>;
  events?: ProcessEventInfo[];
}

export interface MaterialInfo {
  kind: string;
  description?: string | null;
  source?: string | null;
}

export interface BaseMeasurement {
  type: "measurement";
  kind: string;
  value: number | string;
  unit?: string | null;
  uncertainty?: number | null;
  measurement_method?: string | null;
  measurement_statistic?: string | null;
  temperature?: string | null;
  pressure?: string | null;
  description?: string | null;
  source?: string | null;
}

export interface CompositionMeasurement {
  type: "composition";
  formula: string;
  method?: string | null;
  description?: string | null;
  source?: string | null;
}

export interface PhaseMeasurement {
  type: "phase";
  name?: string | null;
  struct?: string | null;
  tags?: string[] | null;
  within?: string | null;
  description?: string | null;
  source?: string | null;
  measurements?: Measurement[];
}

export interface GlobalLatticeParamMeasurement {
  type: "global_lattice_param";
  struct?: string | null;
  name?: string | null;
  lattice_description?: string | null;
  phase_fraction?: string | null;
  description?: string | null;
  source?: string | null;
}

export interface LatticeMeasurement {
  type: "lattice";
  a?: number | null;
  b?: number | null;
  c?: number | null;
  description?: string | null;
  source?: string | null;
}

export type Measurement =
  | BaseMeasurement
  | CompositionMeasurement
  | PhaseMeasurement
  | GlobalLatticeParamMeasurement
  | LatticeMeasurement;

export interface GraphNode {
  id: string;
  type: "material" | "raw_material";
  label: string;
  name?: string | null;
  measurements?: Measurement[];
  materials?: Record<string, MaterialInfo> | null;
  source_code?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  process_steps?: ProcessStep[];
  source_code?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}

export interface DescriptionGroup {
  kinds: string[];
  method?: string | null;
  group_name?: string | null;
  desc?: string | null;
  source?: string | null;
}

export interface Experiment {
  nodes: GraphNode[];
  edges: GraphEdge[];
  descriptions?: DescriptionGroup[];
}

export type GraphData = Record<string, Experiment[]>;

export type SelectedElement =
  | { kind: "node"; data: GraphNode }
  | { kind: "config"; data: PhaseMeasurement; parentLabel: string }
  | { kind: "edge"; data: GraphEdge & { sourceLabel: string; targetLabel: string } }
  | null;
