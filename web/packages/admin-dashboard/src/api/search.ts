import { apiClient } from './client';
import type { SearchResponse } from '@/types/semantic';

const BASE_URL = '/api/v1/search';

/** 搜索 API */
export const searchApi = {
  /** 语义搜索（指标/维度/语义模型） */
  search: (query: string, limit = 10) =>
    apiClient
      .get<SearchResponse>(BASE_URL, {
        params: { q: query, limit },
      })
      .then((res) => res.data),
};
