import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../app/context";
import type { Job, Metadata } from "../api/types";

export function useData<T>(key: string, path: string, enabled = true) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["user", user?.id, key, path],
    queryFn: () => api<T>(path),
    enabled: !!user && enabled,
    retry: false,
    gcTime: 0,
  });
}
export function useMetadata() {
  return useQuery({
    queryKey: ["metadata"],
    queryFn: () => api<Metadata>("/metadata"),
    staleTime: 60000,
  });
}
export function useInvalidate() {
  const client = useQueryClient();
  const { user } = useAuth();
  return useCallback(
    () => client.invalidateQueries({ queryKey: ["user", user?.id] }),
    [client, user?.id],
  );
}
export function useJob(id: string | null) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["user", user?.id, "job", id],
    queryFn: () => api<Job>(`/jobs/${id}`),
    enabled: !!id && !!user,
    retry: false,
    gcTime: 0,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status || "queued")
        ? 2000
        : false,
    refetchIntervalInBackground: false,
  });
}
