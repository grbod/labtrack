import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { usersApi, type UserUpdate } from "@/api/users"
import type { UserProfileUpdate } from "@/types"

// Query keys
export const userKeys = {
  all: ["users"] as const,
  profile: () => [...userKeys.all, "profile"] as const,
  list: () => [...userKeys.all, "list"] as const,
  detail: (id: number) => [...userKeys.all, "detail", id] as const,
}

/**
 * Hook to get the current user's profile.
 */
export function useProfile() {
  return useQuery({
    queryKey: userKeys.profile(),
    queryFn: usersApi.getProfile,
  })
}

/**
 * Hook to update the current user's profile.
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: UserProfileUpdate) => usersApi.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.profile() })
    },
  })
}

/**
 * Hook to list all users (admin only).
 */
export function useUsers() {
  return useQuery({
    queryKey: userKeys.list(),
    queryFn: usersApi.list,
  })
}

/**
 * Hook to get a single user by ID (admin only).
 */
export function useUser(id: number) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => usersApi.get(id),
    enabled: !!id,
  })
}

/**
 * Hook to update a user (admin only).
 */
export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) =>
      usersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all })
    },
  })
}

/**
 * Hook to delete a user (admin only).
 */
export function useDeleteUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => usersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.list() })
    },
  })
}
