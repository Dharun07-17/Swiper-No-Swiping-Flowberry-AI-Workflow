export interface IntegrationSummary {
  id: string;
  provider: string;
  display_name: string;
  created_at: string;
  updated_at: string;
  has_oauth_json: boolean;
  has_api_key: boolean;
  has_oauth_token: boolean;
}
