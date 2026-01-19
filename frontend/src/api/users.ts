import { api } from "./client"
import type { User, UserProfileUpdate, UserRole } from "@/types"

export interface UserUpdate {
  email?: string | null
  full_name?: string | null
  title?: string | null
  phone?: string | null
  role?: UserRole
  is_active?: boolean
  password?: string
}

export const usersApi = {
  /**
   * Get the current user's profile.
   */
  getProfile: async (): Promise<User> => {
    const response = await api.get<User>("/users/me")
    return response.data
  },

  /**
   * Update the current user's profile.
   */
  updateProfile: async (data: UserProfileUpdate): Promise<User> => {
    const response = await api.put<User>("/users/me", data)
    return response.data
  },

  /**
   * List all users (admin only).
   */
  list: async (): Promise<User[]> => {
    const response = await api.get<User[]>("/users")
    return response.data
  },

  /**
   * Get a user by ID (admin only).
   */
  get: async (id: number): Promise<User> => {
    const response = await api.get<User>(`/users/${id}`)
    return response.data
  },

  /**
   * Update a user (admin only).
   */
  update: async (id: number, data: UserUpdate): Promise<User> => {
    const response = await api.patch<User>(`/users/${id}`, data)
    return response.data
  },

  /**
   * Delete a user (admin only).
   */
  delete: async (id: number): Promise<void> => {
    await api.delete(`/users/${id}`)
  },
}
