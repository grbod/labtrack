import { api } from "./client"
import type { User, UserRole } from "@/types"

export interface UserUpdate {
  email?: string | null
  full_name?: string | null
  title?: string | null
  phone?: string | null
  role?: UserRole
  is_active?: boolean
  password?: string
}

export interface UserCreateData {
  username: string
  password: string
  email: string
  role: UserRole
  full_name: string
  title: string
}

export const usersApi = {
  /**
   * Create a new user (admin only).
   */
  create: async (data: UserCreateData): Promise<User> => {
    const response = await api.post<User>("/users", data)
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
