export type Client = {
  id: string;
  organization_id: string;
  name: string;
  vat_number?: string | null;
  status: string;
};

export type Brand = {
  id: string;
  organization_id: string;
  client_id: string;
  name: string;
};

export type RetailChain = {
  id: string;
  organization_id: string;
  name: string;
  insignia?: string | null;
};

export type Store = {
  id: string;
  organization_id: string;
  retail_chain_id: string;
  name: string;
  credential_name?: string | null;
  address?: string | null;
  zone_code: string;
  agency_supervisor_id?: string | null;
};

export type Employee = {
  id: string;
  organization_id: string;
  full_name: string;
  engagement_type: string;
  zone_code: string;
  supervisor_id?: string | null;
  status: string;
  hourly_cost?: string | null;
  email?: string | null;
  phone?: string | null;
};

export type ContractLine = {
  id: string;
  organization_id: string;
  contract_id: string;
  store_id: string;
  service_type: string;
  contracted_hours?: string | null;
  bill_rate?: string | null;
  fixed_amount?: string | null;
  schedule_rules?: Record<string, unknown> | null;
  pricing_components?: Record<string, unknown> | null;
  start_date: string;
  end_date?: string | null;
  generates_daily_shifts: boolean;
};

export type Contract = {
  id: string;
  organization_id: string;
  client_id: string;
  brand_id?: string | null;
  number: string;
  type: string;
  billing_model: string;
  start_date: string;
  end_date?: string | null;
  status: string;
  version: number;
  notes?: string | null;
  lines: ContractLine[];
};

export type Assignment = {
  id: string;
  employee_id: string;
  employee_name?: string | null;
  is_substitute: boolean;
  active: boolean;
};

export type Shift = {
  id: string;
  organization_id: string;
  contract_line_id: string;
  service_plan_id?: string | null;
  store_id: string;
  store_name?: string | null;
  planned_start: string;
  planned_end: string;
  status: string;
  shift_type: string;
  assignments: Assignment[];
};

export type Absence = {
  id: string;
  organization_id: string;
  employee_id: string;
  employee_name?: string | null;
  absence_type: string;
  start_date: string;
  end_date: string;
  status: string;
  reason?: string | null;
};

export type PlanningWeek = {
  week_start: string;
  week_end: string;
  shifts: Shift[];
  employees: Employee[];
  absences?: Absence[];
  unassigned_count?: number;
};

export type AlertItem = {
  kind: string;
  severity: string;
  title: string;
  message: string;
  entity_type: string;
  entity_id: string;
};

export type Substitution = {
  id: string;
  shift_id: string;
  planned_employee_id: string;
  executed_employee_id: string;
  planned_employee_name?: string | null;
  executed_employee_name?: string | null;
  reason?: string | null;
  absence_id?: string | null;
  created_at: string;
};

export type TimeEntry = {
  id: string;
  shift_id: string;
  hours_contracted: string;
  hours_planned: string;
  hours_assigned: string;
  hours_executed: string;
  hours_approved: string;
  hours_billable: string;
  hours_payable: string;
  status: string;
};

export type Organization = {
  id: string;
  name: string;
  timezone: string;
  settings: Record<string, unknown>;
};

export type ServicePlan = {
  id: string;
  organization_id: string;
  contract_line_id: string;
  name: string;
  recurrence_rule: Record<string, unknown>;
  default_employee_id?: string | null;
  active: boolean;
};
