import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  Users,
  Loader2,
  Save,
  X,
  Pencil,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { useUsers, useUpdateUser, userKeys } from "@/hooks/useUsers"
import type { User, UserRole } from "@/types"

// Role display configuration
const ROLE_CONFIG: Record<UserRole, { label: string; color: string }> = {
  admin: { label: "Admin", color: "bg-purple-100 text-purple-800" },
  qc_manager: { label: "QC Manager", color: "bg-blue-100 text-blue-800" },
  lab_tech: { label: "Lab Tech", color: "bg-green-100 text-green-800" },
  read_only: { label: "Read Only", color: "bg-slate-100 text-slate-600" },
}

export function UserManagementPage() {
  const { data: users, isLoading, error } = useUsers()
  const updateUserMutation = useUpdateUser()
  const queryClient = useQueryClient()

  // Edit state
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({
    full_name: "",
    title: "",
    phone: "",
    email: "",
  })

  const handleEditClick = (user: User) => {
    setEditingUser(user)
    setEditForm({
      full_name: user.full_name || "",
      title: user.title || "",
      phone: user.phone || "",
      email: user.email || "",
    })
  }

  const handleSaveEdit = async () => {
    if (!editingUser) return

    try {
      await updateUserMutation.mutateAsync({
        id: editingUser.id,
        data: {
          full_name: editForm.full_name || null,
          title: editForm.title || null,
          phone: editForm.phone || null,
          email: editForm.email || null,
        },
      })
      setEditingUser(null)
    } catch {
      // Error handled by mutation
    }
  }

  const handleCancelEdit = () => {
    setEditingUser(null)
    setEditForm({ full_name: "", title: "", phone: "", email: "" })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <p className="text-slate-500">Failed to load users</p>
          <p className="text-sm text-slate-400 mt-1">{String(error)}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[26px] font-bold text-slate-900 tracking-tight flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100">
                <Users className="h-5 w-5 text-indigo-600" />
              </div>
              User Management
            </h1>
            <p className="mt-1.5 text-[15px] text-slate-500">
              Manage user profiles and COA signing information
            </p>
          </div>
        </div>

        {/* Users Table */}
        <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="font-semibold text-slate-700">Username</TableHead>
                <TableHead className="font-semibold text-slate-700">Full Name</TableHead>
                <TableHead className="font-semibold text-slate-700">Title</TableHead>
                <TableHead className="font-semibold text-slate-700">Email</TableHead>
                <TableHead className="font-semibold text-slate-700">Role</TableHead>
                <TableHead className="font-semibold text-slate-700">Status</TableHead>
                <TableHead className="font-semibold text-slate-700 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users && users.length > 0 ? (
                users.map((user) => (
                  <TableRow key={user.id} className="hover:bg-slate-50/50">
                    <TableCell className="font-medium text-slate-900">
                      {user.username}
                    </TableCell>
                    <TableCell className="text-slate-700">
                      {user.full_name || (
                        <span className="text-slate-400 italic">Not set</span>
                      )}
                    </TableCell>
                    <TableCell className="text-slate-700">
                      {user.title || (
                        <span className="text-slate-400 italic">Not set</span>
                      )}
                    </TableCell>
                    <TableCell className="text-slate-700">
                      {user.email || (
                        <span className="text-slate-400 italic">Not set</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={ROLE_CONFIG[user.role]?.color || "bg-slate-100 text-slate-600"}
                      >
                        {ROLE_CONFIG[user.role]?.label || user.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {user.is_active ? (
                        <Badge variant="secondary" className="bg-green-100 text-green-800">
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="bg-red-100 text-red-800">
                          Inactive
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditClick(user)}
                        className="text-slate-600 hover:text-slate-900"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12 text-slate-500">
                    No users found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Edit User Dialog */}
      <Dialog open={!!editingUser} onOpenChange={(open) => !open && handleCancelEdit()}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit User Profile</DialogTitle>
            <DialogDescription>
              Update the profile information for {editingUser?.username}. This information will appear on COA documents.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-fullname">Full Name</Label>
              <Input
                id="edit-fullname"
                value={editForm.full_name}
                onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                placeholder="Enter full name"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-title">Title</Label>
              <Input
                id="edit-title"
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="e.g., Quality Assurance Manager"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-phone">Phone</Label>
              <Input
                id="edit-phone"
                value={editForm.phone}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="Enter phone number"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-email">Email</Label>
              <Input
                id="edit-email"
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="Enter email address"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelEdit}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={updateUserMutation.isPending}>
              {updateUserMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
