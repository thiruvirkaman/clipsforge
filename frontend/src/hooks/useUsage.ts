import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';
import { UsageSummary, UsageRecordEntry } from '@/types';

/** Fetches the current user's usage summary (plan limits + usage this period). */
export function useUsageSummary() {
  return useQuery({
    queryKey: ['usage', 'me'],
    queryFn: async (): Promise<UsageSummary> => {
      const { data } = await api.get<UsageSummary>('/usage/me');
      return data;
    },
  });
}

/** Fetches the current user's historical usage records, most recent first. */
export function useUsageHistory() {
  return useQuery({
    queryKey: ['usage', 'history'],
    queryFn: async (): Promise<UsageRecordEntry[]> => {
      const { data } = await api.get<UsageRecordEntry[]>('/usage/history');
      return data;
    },
  });
}
