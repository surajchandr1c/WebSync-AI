export interface JobEventResponse {
  id: string;
  job_id: string;
  event_type: string;
  details: Record<string, any>;
  created_at: string;
}

export interface JobEventListResponse {
  items: JobEventResponse[];
  total: number;
  page: number;
  page_size: number;
}
