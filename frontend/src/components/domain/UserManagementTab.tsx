import { useState } from "react"
import { Users, Loader2, Save, Pencil, Plus, KeyRound } from "lucide-react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

import { useUsers, useUpdateUser, useCreateUser } from "@/hooks/useUsers"
import { useAuthStore } from "@/store/auth"
import { toast } from "sonner"
import type { User, UserRole } from "@/types"

const ROLE_CONFIG: Record<UserRole, { label: string; color: string }> = {
  admin: { label: "Admin", color: "bg-purple-100 text-purple-800" },
  qc_manager: { label: "QC Manager", color: "bg-blue-100 text-blue-800" },
  lab_tech: { label: "Lab Tech", color: "bg-green-100 text-green-800" },
  read_only: { label: "Read Only", color: "bg-slate-100 text-slate-600" },
}

interface EditForm {
  full_name: string
  title: string
  phone: string
  email: string
  role: UserRole
  is_active: boolean
}

interface CreateForm {
  username: string
  password: string
  email: string
  full_name: string
  title: string
  role: UserRole
}

const DEFAULT_EDIT_FORM: EditForm = {
  full_name: "",
  title: "",
  phone: "",
  email: "",
  role: "read_only",
  is_active: true,
}

const DEFAULT_CREATE_FORM: CreateForm = {
  username: "",
  password: "",
  email: "",
  full_name: "",
  title: "",
  role: "read_only" as UserRole,
}

export function UserManagementTab() {
  const { data: users, isLoading, error } = useUsers()
  const updateUserMutation = useUpdateUser()
  const createUserMutation = useCreateUser()
  const { user: currentUser } = useAuthStore()

  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState<EditForm>(DEFAULT_EDIT_FORM)
  const [resetPassword, setResetPassword] = useState("")
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [createForm, setCreateForm] = useState<CreateForm>(DEFAULT_CREATE_FORM)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-[13px] text-red-600">
          Failed to load users: {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </div>
    )
  }

  const handleEditClick = (user: User) => {
    setEditingUser(user)
    setEditForm({
      full_name: user.full_name || "",
      title: user.title || "",
      phone: user.phone || "",
      email: user.email || "",
      role: user.role,
      is_active: user.is_active,
    })
    setResetPassword("")
  }

  const handleCancelEdit = () => {
    setEditingUser(null)
    setEditForm(DEFAULT_EDIT_FORM)
    setResetPassword("")
  }

  const handleSaveEdit = async () => {
    if (!editingUser) return

    try {
      await updateUserMutation.mutateAsync({
        id: editingUser.id,
        data: {
          full_name: editForm.full_name,
          title: editForm.title,
          phone: editForm.phone,
          email: editForm.email,
          role: editForm.role,
          is_active: editForm.is_active,
        },
      })
      toast.success("User updated successfully")
      handleCancelEdit()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to update user")
    }
  }

  const handleResetPassword = async () => {
    if (!editingUser) return

    if (resetPassword.length < 6) {
      toast.error("Password must be at least 6 characters")
      return
    }

    try {
      await updateUserMutation.mutateAsync({
        id: editingUser.id,
        data: { password: resetPassword },
      })
      toast.success("Password reset successfully")
      setResetPassword("")
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to reset password")
    }
  }

  const handleCreateUser = async () => {
    if (!createForm.username || createForm.username.length < 3) {
      toast.error("Username must be at least 3 characters")
      return
    }
    if (createForm.password.length < 6) {
      toast.error("Password must be at least 6 characters")
      return
    }
    if (!createForm.email || !createForm.email.includes("@")) {
      toast.error("A valid email is required")
      return
    }
    if (!createForm.full_name) {
      toast.error("Full name is required")
      return
    }
    if (!createForm.title) {
      toast.error("Title is required")
      return
    }
    try {
      await createUserMutation.mutateAsync(createForm)
      toast.success("User created successfully")
      setShowCreateDialog(false)
      setCreateForm(DEFAULT_CREATE_FORM)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to create user")
    }
  }

  return (
    <>
      <Card className="border-slate-200/60 shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100">
                <Users className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  User Management
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Manage user accounts, roles, and access
                </CardDescription>
              </div>
            </div>
            <Button onClick={() => setShowCreateDialog(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              Create User
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[13px] font-semibold">Username</TableHead>
                  <TableHead className="text-[13px] font-semibold">Full Name</TableHead>
                  <TableHead className="text-[13px] font-semibold">Email</TableHead>
                  <TableHead className="text-[13px] font-semibold">Role</TableHead>
                  <TableHead className="text-[13px] font-semibold">Status</TableHead>
                  <TableHead className="text-[13px] font-semibold">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users?.map((user) => {
                  const roleConfig = ROLE_CONFIG[user.role]
                  return (
                    <TableRow key={user.id}>
                      <TableCell className="text-[13px] font-medium text-slate-900">
                        {user.username}
                      </TableCell>
                      <TableCell className="text-[13px] text-slate-700">
                        {user.full_name || "—"}
                      </TableCell>
                      <TableCell className="text-[13px] text-slate-600">
                        {user.email || "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={`text-[11px] font-medium ${roleConfig.color}`}
                        >
                          {roleConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.is_active ? (
                          <Badge
                            variant="secondary"
                            className="bg-green-100 text-green-800 text-[11px] font-medium"
                          >
                            Active
                          </Badge>
                        ) : (
                          <Badge
                            variant="secondary"
                            className="bg-red-100 text-red-800 text-[11px] font-medium"
                          >
                            Inactive
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditClick(user)}
                          className="h-8 w-8 p-0"
                        >
                          <Pencil className="h-4 w-4 text-slate-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
                {users?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-[13px] text-slate-500">
                      No users found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Create User Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create New User</DialogTitle>
            <DialogDescription>
              All fields are required. The user will be able to change their password after logging in.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-1.5">
              <Label htmlFor="create-username" className="text-[13px] font-semibold text-slate-700">
                Username
              </Label>
              <Input
                id="create-username"
                value={createForm.username}
                onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="Enter username"
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-password" className="text-[13px] font-semibold text-slate-700">
                Password
              </Label>
              <Input
                id="create-password"
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Min 6 characters"
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-email" className="text-[13px] font-semibold text-slate-700">
                Email
              </Label>
              <Input
                id="create-email"
                type="email"
                value={createForm.email}
                onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="Enter email"
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-fullname" className="text-[13px] font-semibold text-slate-700">
                Full Name
              </Label>
              <Input
                id="create-fullname"
                value={createForm.full_name}
                onChange={(e) => setCreateForm((f) => ({ ...f, full_name: e.target.value }))}
                placeholder="Enter full name"
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-title" className="text-[13px] font-semibold text-slate-700">
                Title
              </Label>
              <Input
                id="create-title"
                value={createForm.title}
                onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="e.g., Lab Technician"
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-role" className="text-[13px] font-semibold text-slate-700">
                Role
              </Label>
              <Select
                value={createForm.role}
                onValueChange={(val) => setCreateForm((f) => ({ ...f, role: val as UserRole }))}
              >
                <SelectTrigger className="h-10 border-slate-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="qc_manager">QC Manager</SelectItem>
                  <SelectItem value="lab_tech">Lab Tech</SelectItem>
                  <SelectItem value="read_only">Read Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateDialog(false)
                setCreateForm(DEFAULT_CREATE_FORM)
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateUser}
              disabled={createUserMutation.isPending}
              className="gap-2"
            >
              {createUserMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Create User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={editingUser !== null} onOpenChange={(open) => { if (!open) handleCancelEdit() }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>
              Update profile, role, and access for {editingUser?.username}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-1.5">
              <Label htmlFor="edit-fullname" className="text-[13px] font-semibold text-slate-700">
                Full Name
              </Label>
              <Input
                id="edit-fullname"
                value={editForm.full_name}
                onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-title" className="text-[13px] font-semibold text-slate-700">
                Title
              </Label>
              <Input
                id="edit-title"
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-phone" className="text-[13px] font-semibold text-slate-700">
                Phone
              </Label>
              <Input
                id="edit-phone"
                value={editForm.phone}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-email" className="text-[13px] font-semibold text-slate-700">
                Email
              </Label>
              <Input
                id="edit-email"
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                className="h-10 border-slate-200"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-role" className="text-[13px] font-semibold text-slate-700">
                Role
              </Label>
              <Select
                value={editForm.role}
                onValueChange={(val) => setEditForm((f) => ({ ...f, role: val as UserRole }))}
              >
                <SelectTrigger className="h-10 border-slate-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="qc_manager">QC Manager</SelectItem>
                  <SelectItem value="lab_tech">Lab Tech</SelectItem>
                  <SelectItem value="read_only">Read Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="edit-active" className="text-[13px] font-semibold text-slate-700">
                  Active
                </Label>
                {editingUser?.id === currentUser?.id && (
                  <p className="text-[11px] text-slate-500">Cannot deactivate your own account</p>
                )}
              </div>
              <Switch
                id="edit-active"
                checked={editForm.is_active}
                onCheckedChange={(checked) => setEditForm((f) => ({ ...f, is_active: checked }))}
                disabled={editingUser?.id === currentUser?.id}
              />
            </div>

            {/* Metadata */}
            {editingUser && (
              <div className="rounded-lg bg-slate-50 p-3 space-y-1">
                <p className="text-[11px] text-slate-500">
                  Created: {new Date(editingUser.created_at).toLocaleDateString()}
                </p>
                {editingUser.updated_at && (
                  <p className="text-[11px] text-slate-500">
                    Last updated: {new Date(editingUser.updated_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            )}

            {/* Reset Password */}
            <div className="border-t border-slate-200 pt-4 mt-2">
              <Label className="text-[13px] font-semibold text-slate-700">Reset Password</Label>
              <div className="flex gap-2 mt-1.5">
                <Input
                  type="password"
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  placeholder="New temporary password"
                  className="h-10 border-slate-200"
                />
                <Button
                  variant="outline"
                  onClick={handleResetPassword}
                  disabled={updateUserMutation.isPending}
                  className="gap-2 shrink-0"
                >
                  {updateUserMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <KeyRound className="h-4 w-4" />
                  )}
                  Reset
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCancelEdit}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={updateUserMutation.isPending}
              className="gap-2"
            >
              {updateUserMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
