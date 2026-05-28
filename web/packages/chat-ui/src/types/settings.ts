export interface UserSettings {
  theme: 'light' | 'dark' | 'system';
  defaultDialect: 'mysql' | 'postgresql' | 'clickhouse';
  defaultTenantId: string;
}
