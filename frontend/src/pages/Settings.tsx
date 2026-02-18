import { useState, useEffect, useRef, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Settings as SettingsIcon,
  Building2,
  AlertTriangle,
  Eye,
  Save,
  Loader2,
  Upload,
  Mail,
  RotateCcw,
  Info,
  ListOrdered,
  UserCircle,
  Users,
  KeyRound,
  Trash2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"

import { useAuthStore } from "@/store/auth"
import { useSettings, PAGE_SIZE_OPTIONS } from "@/hooks/useSettings"
import { useLabMapping, useRebuildLabMapping } from "@/hooks/useLabMapping"
import { useChangePassword } from "@/hooks/useUsers"
import { emailTemplateApi } from "@/api/emailTemplate"
import { authApi } from "@/api/client"
import { useLabInfo } from "@/hooks/useLabInfo"
import { COACategoryOrderEditor } from "@/components/domain/COACategoryOrderEditor"
import { UserManagementTab } from "@/components/domain/UserManagementTab"
import { ImageCropper } from "@/components/ui/image-cropper"
import { toast } from "sonner"
import type { EmailTemplateVariable } from "@/types/emailTemplate"
import type { User } from "@/types"

type SettingsTab = "display" | "system" | "user" | "email" | "coa-style" | "lab-mapping" | "user-management"

export function SettingsPage() {
  const { user } = useAuthStore()
  const { user: userSettings, system: systemSettings, canEditSystemSettings } = useSettings(
    user?.username,
    user?.role
  )
  const queryClient = useQueryClient()

  // Tab state
  const [activeTab, setActiveTab] = useState<SettingsTab>("display")

  // Local form state for system settings
  const [staleWarningDays, setStaleWarningDays] = useState(systemSettings.settings.staleWarningDays)
  const [staleCriticalDays, setStaleCriticalDays] = useState(systemSettings.settings.staleCriticalDays)
  const [recentlyCompletedDays, setRecentlyCompletedDays] = useState(systemSettings.settings.recentlyCompletedDays)
  const [companyName, setCompanyName] = useState(systemSettings.settings.labInfo.companyName)
  const [address, setAddress] = useState(systemSettings.settings.labInfo.address)
  const [phone, setPhone] = useState(systemSettings.settings.labInfo.phone)
  const [email, setEmail] = useState(systemSettings.settings.labInfo.email)
  const [city, setCity] = useState("")
  const [state, setState] = useState("")
  const [zipCode, setZipCode] = useState("")
  const [requirePdfForSubmission, setRequirePdfForSubmission] = useState(true)
  const [labInfoDirty, setLabInfoDirty] = useState(false)
  const [labInfoAutoSaveSuccess, setLabInfoAutoSaveSuccess] = useState(false)

  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    if (labInfoDirty) {
      setLabInfoAutoSaveSuccess(false)
    }
  }, [labInfoDirty])

  // Lab info from backend
  const {
    labInfo,
    isLoading: labInfoLoading,
    updateMutation: updateLabInfoMutation,
    uploadLogoMutation,
    deleteLogoMutation,
  } = useLabInfo()
  const logoInputRef = useRef<HTMLInputElement>(null)

  // Image cropper state for logo
  const [cropperOpen, setCropperOpen] = useState(false)
  const [imageToCrop, setImageToCrop] = useState<string | null>(null)
  const [isUploadingLogo, setIsUploadingLogo] = useState(false)

  // User profile state
  const [userFullName, setUserFullName] = useState(user?.full_name || "")
  const [userTitle, setUserTitle] = useState(user?.title || "")
  const [userPhone, setUserPhone] = useState(user?.phone || "")
  const [userEmail, setUserEmail] = useState(user?.email || "")
  const [isUserSaving, setIsUserSaving] = useState(false)
  const [userSaveSuccess, setUserSaveSuccess] = useState(false)
  const signatureInputRef = useRef<HTMLInputElement>(null)

  // Signature cropper state
  const [signatureCropperOpen, setSignatureCropperOpen] = useState(false)
  const [signatureToCrop, setSignatureToCrop] = useState<string | null>(null)

  // Change password state
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const changePasswordMutation = useChangePassword()

  // Email template state
  const [emailSubject, setEmailSubject] = useState("")
  const [emailBody, setEmailBody] = useState("")
  const subjectInputRef = useRef<HTMLInputElement>(null)
  const bodyTextareaRef = useRef<HTMLTextAreaElement>(null)

  // Fetch email template
  const { data: emailTemplate, isLoading: isLoadingTemplate } = useQuery({
    queryKey: ["emailTemplate"],
    queryFn: emailTemplateApi.get,
    enabled: canEditSystemSettings,
  })

  // Fetch available variables
  const { data: variablesData } = useQuery({
    queryKey: ["emailTemplateVariables"],
    queryFn: emailTemplateApi.getVariables,
    enabled: canEditSystemSettings,
  })

  // Preview query - debounced
  const { data: preview } = useQuery({
    queryKey: ["emailTemplatePreview", emailSubject, emailBody],
    queryFn: () => emailTemplateApi.preview({ subject: emailSubject, body: emailBody }),
    enabled: canEditSystemSettings && emailSubject.length > 0 && emailBody.length > 0,
  })

  const {
    data: labMappingData,
    isLoading: isLabMappingLoading,
  } = useLabMapping(activeTab === "lab-mapping")
  const rebuildMappingMutation = useRebuildLabMapping()

  // Update email template mutation
  const updateTemplateMutation = useMutation({
    mutationFn: emailTemplateApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["emailTemplate"] })
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    },
  })

  // Reset to defaults mutation
  const resetTemplateMutation = useMutation({
    mutationFn: emailTemplateApi.reset,
    onSuccess: (data) => {
      setEmailSubject(data.subject)
      setEmailBody(data.body)
      queryClient.invalidateQueries({ queryKey: ["emailTemplate"] })
    },
  })

  // Sync local state when template loads
  useEffect(() => {
    if (emailTemplate) {
      setEmailSubject(emailTemplate.subject)
      setEmailBody(emailTemplate.body)
    }
  }, [emailTemplate])

  // Sync local state when system settings change (for thresholds)
  useEffect(() => {
    setStaleWarningDays(systemSettings.settings.staleWarningDays)
    setStaleCriticalDays(systemSettings.settings.staleCriticalDays)
    setRecentlyCompletedDays(systemSettings.settings.recentlyCompletedDays)
  }, [systemSettings.settings])

  // Sync local state when lab info loads from backend
  useEffect(() => {
    if (labInfo) {
      setCompanyName(labInfo.company_name)
      setAddress(labInfo.address)
      setPhone(labInfo.phone)
      setEmail(labInfo.email)
      setCity(labInfo.city)
      setState(labInfo.state)
      setZipCode(labInfo.zip_code)
      setRequirePdfForSubmission(labInfo.require_pdf_for_submission)
      setLabInfoDirty(false) // Reset dirty flag when data syncs from API
    }
  }, [labInfo])

  // Sync user profile state when user changes
  useEffect(() => {
    if (user) {
      setUserFullName(user.full_name || "")
      setUserTitle(user.title || "")
      setUserPhone(user.phone || "")
      setUserEmail(user.email || "")
    }
  }, [user])

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value, 10)
    userSettings.updateSettings({ pageSize: value })
  }

  const handleSaveSystemSettings = async () => {
    setIsSaving(true)
    setSaveSuccess(false)

    try {
      // Validate thresholds
      const warning = Math.max(1, staleWarningDays)
      const critical = Math.max(warning + 1, staleCriticalDays)
      const recentlyCompleted = Math.max(1, recentlyCompletedDays)

      // Save thresholds to localStorage
      systemSettings.updateSettings({
        staleWarningDays: warning,
        staleCriticalDays: critical,
        recentlyCompletedDays: recentlyCompleted,
      })

      // Save lab info to backend API
      await updateLabInfoMutation.mutateAsync({
        company_name: companyName,
        address,
        phone,
        email,
        city,
        state,
        zip_code: zipCode,
        require_pdf_for_submission: requirePdfForSubmission,
      })

      setLabInfoDirty(false) // Reset dirty flag on successful save
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (error) {
      console.error("Failed to save settings:", error)
    } finally {
      setIsSaving(false)
    }
  }

  // Logo upload handler - opens cropper
  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ["image/jpeg", "image/png", "image/webp"]
    if (!allowedTypes.includes(file.type)) {
      alert("Please upload a JPG, PNG, or WebP image")
      return
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert("Image must be less than 2MB")
      return
    }

    // Create object URL for cropper
    const imageUrl = URL.createObjectURL(file)
    setImageToCrop(imageUrl)
    setCropperOpen(true)

    // Reset file input
    if (logoInputRef.current) {
      logoInputRef.current.value = ""
    }
  }

  // Handle cropped image upload
  const handleCropComplete = async (croppedBlob: Blob) => {
    // Convert blob to File for upload
    const file = new File([croppedBlob], "logo.png", { type: "image/png" })

    setIsUploadingLogo(true)
    try {
      await uploadLogoMutation.mutateAsync(file)
      setLabInfoAutoSaveSuccess(true)
      setTimeout(() => setLabInfoAutoSaveSuccess(false), 2000)
      // Success! Dialog will close via onOpenChange(false) in ImageCropper
      // URL cleanup happens in onOpenChange callback when dialog closes
    } catch (error: any) {
      console.error("Logo upload failed:", error?.response?.data || error)
      const message = error?.response?.data?.detail
        || error?.response?.statusText
        || error?.message
        || "Unknown error"
      alert(`Failed to upload logo: ${message}\n\nStatus: ${error?.response?.status || 'N/A'}`)
      throw error // Re-throw so ImageCropper doesn't close the dialog
    } finally {
      setIsUploadingLogo(false)
    }
  }

  // Logo delete handler
  const handleDeleteLogo = async () => {
    try {
      await deleteLogoMutation.mutateAsync()
      setLabInfoAutoSaveSuccess(true)
      setTimeout(() => setLabInfoAutoSaveSuccess(false), 2000)
    } catch {
      // Error handled by mutation
    }
  }

  const handleSaveEmailTemplate = () => {
    updateTemplateMutation.mutate({
      subject: emailSubject,
      body: emailBody,
    })
  }

  const handleResetEmailTemplate = () => {
    resetTemplateMutation.mutate()
  }

  // User profile handlers
  const handleSaveUserProfile = async () => {
    setIsUserSaving(true)
    setUserSaveSuccess(false)
    try {
      await authApi.updateProfile({
        full_name: userFullName || null,
        title: userTitle || null,
        phone: userPhone || null,
      })
      // Refresh Zustand auth store so the rest of the app sees updated user data
      await useAuthStore.getState().checkAuth()
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
      setUserSaveSuccess(true)
      setTimeout(() => setUserSaveSuccess(false), 2000)
    } catch {
      // Error handled by toast or notification
    } finally {
      setIsUserSaving(false)
    }
  }

  // Signature upload handler - opens cropper
  const handleSignatureUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"]
    if (!allowedTypes.includes(file.type)) {
      alert("Please upload a JPG, PNG, or WebP image")
      return
    }

    if (file.size > 2 * 1024 * 1024) {
      alert("Image must be less than 2MB")
      return
    }

    const imageUrl = URL.createObjectURL(file)
    setSignatureToCrop(imageUrl)
    setSignatureCropperOpen(true)

    if (signatureInputRef.current) {
      signatureInputRef.current.value = ""
    }
  }

  // Handle cropped signature upload
  const handleSignatureCropComplete = async (croppedBlob: Blob) => {
    const file = new File([croppedBlob], "signature.png", { type: "image/png" })

    try {
      await authApi.uploadSignature(file)
      await useAuthStore.getState().checkAuth()
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
      // Success! Dialog will close via onOpenChange(false) in ImageCropper
      // URL cleanup happens in onOpenChange callback when dialog closes
    } catch (error) {
      console.error("Signature upload failed:", error)
      throw error // Re-throw so ImageCropper doesn't close the dialog
    }
  }

  // Signature delete handler
  const handleDeleteSignature = async () => {
    try {
      await authApi.deleteSignature()
      await useAuthStore.getState().checkAuth()
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
    } catch {
      // Error handled
    }
  }

  const insertVariable = useCallback((variable: string, target: "subject" | "body") => {
    const variableText = `{${variable}}`

    if (target === "subject" && subjectInputRef.current) {
      const input = subjectInputRef.current
      const start = input.selectionStart || 0
      const end = input.selectionEnd || 0
      const newValue = emailSubject.slice(0, start) + variableText + emailSubject.slice(end)
      setEmailSubject(newValue)
      // Restore cursor position after state update
      setTimeout(() => {
        input.setSelectionRange(start + variableText.length, start + variableText.length)
        input.focus()
      }, 0)
    } else if (target === "body" && bodyTextareaRef.current) {
      const textarea = bodyTextareaRef.current
      const start = textarea.selectionStart || 0
      const end = textarea.selectionEnd || 0
      const newValue = emailBody.slice(0, start) + variableText + emailBody.slice(end)
      setEmailBody(newValue)
      // Restore cursor position after state update
      setTimeout(() => {
        textarea.setSelectionRange(start + variableText.length, start + variableText.length)
        textarea.focus()
      }, 0)
    }
  }, [emailSubject, emailBody])

  const hasSystemChanges =
    staleWarningDays !== systemSettings.settings.staleWarningDays ||
    staleCriticalDays !== systemSettings.settings.staleCriticalDays ||
    recentlyCompletedDays !== systemSettings.settings.recentlyCompletedDays ||
    labInfoDirty

  const hasUserProfileChanges =
    (user && userFullName !== (user.full_name || "")) ||
    (user && userTitle !== (user.title || "")) ||
    (user && userPhone !== (user.phone || ""))

  const hasEmailChanges =
    emailTemplate &&
    (emailSubject !== emailTemplate.subject || emailBody !== emailTemplate.body)

  const variables = variablesData?.variables || []

  // Tab items
  const tabs: { id: SettingsTab; label: string; icon: React.ReactNode; adminOnly?: boolean }[] = [
    { id: "display", label: "Display", icon: <Eye className="h-4 w-4" /> },
    { id: "user", label: "User Profile", icon: <UserCircle className="h-4 w-4" /> },
    { id: "user-management", label: "User Management", icon: <Users className="h-4 w-4" />, adminOnly: true },
    { id: "system", label: "System", icon: <SettingsIcon className="h-4 w-4" />, adminOnly: true },
    { id: "coa-style", label: "COA Style", icon: <ListOrdered className="h-4 w-4" />, adminOnly: true },
    { id: "email", label: "Customer Email", icon: <Mail className="h-4 w-4" />, adminOnly: true },
    { id: "lab-mapping", label: "Lab Mapping", icon: <Building2 className="h-4 w-4" /> },
  ]

  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || canEditSystemSettings)

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Settings</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Manage your display preferences and system configuration
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 border-b-2 pb-3 pt-1 text-[14px] font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Display Preferences Tab */}
      {activeTab === "display" && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
                <Eye className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  Display Preferences
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Customize how data is displayed throughout the application
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="max-w-sm">
              <Label
                htmlFor="pageSize"
                className="text-[13px] font-semibold text-slate-700"
              >
                Items per page
              </Label>
              <div className="mt-1.5 flex items-center gap-3">
                <select
                  id="pageSize"
                  value={userSettings.settings.pageSize}
                  onChange={handlePageSizeChange}
                  className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-[14px] text-slate-900 shadow-sm focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-900/10"
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size} items
                    </option>
                  ))}
                </select>
                <span className="text-[13px] text-slate-500">per page</span>
              </div>
              <p className="mt-2 text-[12px] text-slate-500">
                Controls the number of items shown in tables and lists
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* User Profile Tab */}
      {activeTab === "user" && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100">
                <UserCircle className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  User Profile
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Your personal information and signature for COA documents
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label
                  htmlFor="userFullName"
                  className="text-[13px] font-semibold text-slate-700"
                >
                  Full Name
                </Label>
                <Input
                  id="userFullName"
                  value={userFullName}
                  onChange={(e) => setUserFullName(e.target.value)}
                  placeholder="Enter your full name"
                  className="h-10 border-slate-200"
                />
              </div>
              <div className="space-y-1.5">
                <Label
                  htmlFor="userTitle"
                  className="text-[13px] font-semibold text-slate-700"
                >
                  Title
                </Label>
                <Input
                  id="userTitle"
                  value={userTitle}
                  onChange={(e) => setUserTitle(e.target.value)}
                  placeholder="e.g., Quality Manager"
                  className="h-10 border-slate-200"
                />
              </div>
              <div className="space-y-1.5">
                <Label
                  htmlFor="userPhone"
                  className="text-[13px] font-semibold text-slate-700"
                >
                  Phone
                </Label>
                <Input
                  id="userPhone"
                  type="tel"
                  value={userPhone}
                  onChange={(e) => setUserPhone(e.target.value)}
                  placeholder="Enter phone number"
                  className="h-10 border-slate-200"
                />
              </div>
              <div className="space-y-1.5">
                <Label
                  htmlFor="userEmailField"
                  className="text-[13px] font-semibold text-slate-700"
                >
                  Email
                </Label>
                <Input
                  id="userEmailField"
                  type="email"
                  value={userEmail}
                  disabled
                  className="h-10 border-slate-200 bg-slate-50 text-slate-500"
                />
                <p className="text-[11px] text-slate-400">
                  Contact an admin to update your email address
                </p>
              </div>
              <div className="sm:col-span-2 space-y-1.5">
                <Label className="text-[13px] font-semibold text-slate-700">
                  Signature
                </Label>
                <div className="flex items-center gap-3">
                  {user?.signature_url && (
                    <img
                      src={user.signature_url}
                      alt="Your signature"
                      className="h-16 w-auto object-contain border rounded bg-white p-1"
                    />
                  )}
                  <input
                    ref={signatureInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleSignatureUpload}
                    className="hidden"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => signatureInputRef.current?.click()}
                    className="gap-2"
                  >
                    <Upload className="h-4 w-4" />
                    {user?.signature_url ? "Change Signature" : "Upload Signature"}
                  </Button>
                  {user?.signature_url && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleDeleteSignature}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <p className="text-[12px] text-slate-500">
                  Recommended: PNG with transparent background. Will appear on released COAs.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-6 mt-4 border-t border-slate-200">
              <Button
                onClick={handleSaveUserProfile}
                disabled={isUserSaving || !hasUserProfileChanges}
                className="gap-2"
              >
                {isUserSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Changes
              </Button>
              {userSaveSuccess && (
                <span className="text-[13px] text-green-600">Changes saved!</span>
              )}
              {!hasUserProfileChanges && !userSaveSuccess && (
                <span className="text-[13px] text-slate-400">No unsaved changes</span>
              )}
            </div>

            {/* Change Password */}
            <div className="pt-6 mt-6 border-t border-slate-200">
              <div className="flex items-center gap-2 mb-4">
                <KeyRound className="h-4 w-4 text-slate-500" />
                <h3 className="text-[14px] font-semibold text-slate-800">Change Password</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl">
                <div className="space-y-1.5">
                  <Label htmlFor="currentPassword" className="text-[13px] font-semibold text-slate-700">
                    Current Password
                  </Label>
                  <Input
                    id="currentPassword"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter current password"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="newPassword" className="text-[13px] font-semibold text-slate-700">
                    New Password
                  </Label>
                  <Input
                    id="newPassword"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min 6 characters"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="confirmPassword" className="text-[13px] font-semibold text-slate-700">
                    Confirm New Password
                  </Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="h-10 border-slate-200"
                  />
                </div>
              </div>
              <div className="mt-4">
                <Button
                  onClick={async () => {
                    if (!currentPassword || !newPassword || !confirmPassword) {
                      toast.error("All password fields are required")
                      return
                    }
                    if (newPassword.length < 6) {
                      toast.error("New password must be at least 6 characters")
                      return
                    }
                    if (newPassword !== confirmPassword) {
                      toast.error("New passwords do not match")
                      return
                    }
                    try {
                      await changePasswordMutation.mutateAsync({ currentPassword, newPassword })
                      toast.success("Password changed successfully")
                      setCurrentPassword("")
                      setNewPassword("")
                      setConfirmPassword("")
                    } catch (err: any) {
                      toast.error(err?.response?.data?.detail || "Failed to change password")
                    }
                  }}
                  disabled={changePasswordMutation.isPending}
                  variant="outline"
                  className="gap-2"
                >
                  {changePasswordMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <KeyRound className="h-4 w-4" />
                  )}
                  Change Password
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Signature Cropper Modal */}
      {signatureToCrop && (
        <ImageCropper
          open={signatureCropperOpen}
          onOpenChange={(open) => {
            setSignatureCropperOpen(open)
            if (!open && signatureToCrop) {
              URL.revokeObjectURL(signatureToCrop)
              setSignatureToCrop(null)
            }
          }}
          imageSrc={signatureToCrop}
          onCropComplete={handleSignatureCropComplete}
          title="Crop Signature"
        />
      )}

      {/* User Management Tab */}
      {activeTab === "user-management" && canEditSystemSettings && (
        <UserManagementTab />
      )}

      {/* System Settings Tab */}
      {activeTab === "system" && canEditSystemSettings && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100">
                <SettingsIcon className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  System Settings
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Configure global settings for the COA system
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2 space-y-8">
            {/* Stale Thresholds */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h3 className="text-[14px] font-semibold text-slate-800">
                  Sample Tracker Thresholds
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-2xl">
                <div className="space-y-1.5">
                  <Label
                    htmlFor="staleWarning"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Stale Warning (days)
                  </Label>
                  <Input
                    id="staleWarning"
                    type="number"
                    min={1}
                    value={staleWarningDays}
                    onChange={(e) => setStaleWarningDays(parseInt(e.target.value, 10) || 1)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Samples older than this show orange warning
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="staleCritical"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Stale Critical (days)
                  </Label>
                  <Input
                    id="staleCritical"
                    type="number"
                    min={staleWarningDays + 1}
                    value={staleCriticalDays}
                    onChange={(e) => setStaleCriticalDays(parseInt(e.target.value, 10) || staleWarningDays + 1)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Samples older than this show red critical
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="recentlyCompleted"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Recently Completed (days)
                  </Label>
                  <Input
                    id="recentlyCompleted"
                    type="number"
                    min={1}
                    value={recentlyCompletedDays}
                    onChange={(e) => setRecentlyCompletedDays(parseInt(e.target.value, 10) || 7)}
                    className="h-10 border-slate-200"
                  />
                  <p className="text-[11px] text-slate-500">
                    Show completed samples from the last X days
                  </p>
                </div>
              </div>
            </div>

            {/* Lab Information */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Building2 className="h-4 w-4 text-blue-500" />
                <h3 className="text-[14px] font-semibold text-slate-800">
                  Lab Information
                </h3>
              </div>
              <p className="text-[12px] text-slate-500 mb-4">
                This information will appear on generated Certificates of Analysis
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
                <div className="sm:col-span-2 space-y-1.5">
                  <Label
                    htmlFor="companyName"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Company Name
                  </Label>
                  <Input
                    id="companyName"
                    value={companyName}
                    onChange={(e) => {
                      setCompanyName(e.target.value)
                      setLabInfoDirty(true)
                    }}
                    placeholder="Enter company name"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label
                    htmlFor="address"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Street Address
                  </Label>
                  <Input
                    id="address"
                    value={address}
                    onChange={(e) => {
                      setAddress(e.target.value)
                      setLabInfoDirty(true)
                    }}
                    placeholder="Enter street address"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="city"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    City
                  </Label>
                  <Input
                    id="city"
                    value={city}
                    onChange={(e) => {
                      setCity(e.target.value)
                      setLabInfoDirty(true)
                    }}
                    placeholder="City"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="state"
                      className="text-[13px] font-semibold text-slate-700"
                    >
                      State
                    </Label>
                    <Input
                      id="state"
                      value={state}
                      onChange={(e) => {
                        setState(e.target.value)
                        setLabInfoDirty(true)
                      }}
                      placeholder="FL"
                      className="h-10 border-slate-200"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="zipCode"
                      className="text-[13px] font-semibold text-slate-700"
                    >
                      ZIP Code
                    </Label>
                    <Input
                      id="zipCode"
                      value={zipCode}
                      onChange={(e) => {
                        setZipCode(e.target.value)
                        setLabInfoDirty(true)
                      }}
                      placeholder="12345"
                      className="h-10 border-slate-200"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="phone"
                      className="text-[13px] font-semibold text-slate-700"
                    >
                      Phone
                    </Label>
                    <Input
                      id="phone"
                      value={phone}
                      onChange={(e) => {
                        setPhone(e.target.value)
                        setLabInfoDirty(true)
                      }}
                      placeholder="(555) 123-4567"
                      className="h-10 border-slate-200"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label
                      htmlFor="email"
                      className="text-[13px] font-semibold text-slate-700"
                    >
                      Email
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value)
                        setLabInfoDirty(true)
                      }}
                      placeholder="lab@company.com"
                      className="h-10 border-slate-200"
                    />
                  </div>
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label className="text-[13px] font-semibold text-slate-700">
                    Company Logo
                  </Label>
                  <div className="flex items-center gap-3">
                    {labInfo?.logo_url && (
                      <img
                        src={labInfo.logo_url}
                        alt="Company logo"
                        className="h-10 w-auto object-contain border rounded"
                      />
                    )}
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleLogoUpload}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => logoInputRef.current?.click()}
                      disabled={uploadLogoMutation.isPending || isUploadingLogo}
                      className="h-10 border-slate-200"
                    >
                      {(uploadLogoMutation.isPending || isUploadingLogo) ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4 mr-2" />
                      )}
                      {labInfo?.logo_url ? "Change Logo" : "Upload Logo"}
                    </Button>
                    {labInfo?.logo_url && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={handleDeleteLogo}
                        disabled={deleteLogoMutation.isPending}
                        className="h-10 text-red-500 hover:text-red-600 hover:bg-red-50"
                      >
                        {deleteLogoMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          "Remove"
                        )}
                      </Button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Recommended: PNG or JPG, max 2MB. Changes save automatically and appear above company name on COAs.
                  </p>
                </div>
              </div>
            </div>

            {/* Submission Settings */}
            <div className="space-y-4 pt-4 border-t border-slate-100">
              <h3 className="text-[14px] font-semibold text-slate-900">Submission Settings</h3>
              <div className="flex items-start gap-3">
                <Switch
                  id="requirePdf"
                  checked={requirePdfForSubmission}
                  onCheckedChange={(checked) => {
                    setRequirePdfForSubmission(checked)
                    setLabInfoDirty(true)
                  }}
                  className="mt-0.5"
                />
                <div className="space-y-1">
                  <Label htmlFor="requirePdf" className="text-[13px] font-semibold text-slate-700">
                    Require PDF for Submission
                  </Label>
                  <p className="text-[11px] text-slate-500">
                    When enabled, at least one lab PDF must be attached before submitting for approval. Admin or QC Manager can override.
                  </p>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="pt-4 border-t border-slate-100">
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleSaveSystemSettings}
                  disabled={isSaving || !hasSystemChanges}
                  className={`${
                    hasSystemChanges
                      ? "bg-blue-600 hover:bg-blue-700"
                      : "bg-slate-400"
                  } text-white shadow-sm h-10 px-5`}
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </Button>
                {saveSuccess && (
                  <span className="text-[13px] font-medium text-emerald-600">
                    Settings saved successfully
                  </span>
                )}
                {!saveSuccess && labInfoAutoSaveSuccess && (
                  <span className="text-[12px] text-emerald-600">
                    Changes saved automatically
                  </span>
                )}
                {!hasSystemChanges && !saveSuccess && !labInfoAutoSaveSuccess && (
                  <span className="text-[12px] text-slate-400">
                    No unsaved changes
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* COA Style Tab */}
      {activeTab === "coa-style" && canEditSystemSettings && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100">
                <ListOrdered className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  COA Display Order
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Configure how test categories are ordered on generated COA documents
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            <COACategoryOrderEditor />
          </CardContent>
        </Card>
      )}

      {/* Customer Email Tab */}
      {activeTab === "email" && canEditSystemSettings && (
        <div className="space-y-6">
          {isLoadingTemplate ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              {/* Email Template Editor */}
              <Card className="border-slate-200/60 shadow-sm">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100">
                      <Mail className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <CardTitle className="text-[16px] font-semibold text-slate-900">
                        Email Template
                      </CardTitle>
                      <CardDescription className="text-[13px] text-slate-500">
                        Customize the email sent with COA documents to customers
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-2 space-y-6">
                  {/* Variable Chips Reference */}
                  <div className="rounded-lg bg-slate-50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Info className="h-4 w-4 text-slate-500" />
                      <span className="text-[13px] font-semibold text-slate-700">
                        Available Variables
                      </span>
                    </div>
                    <p className="text-[12px] text-slate-500 mb-3">
                      Click a variable to insert it at the cursor position, or type it manually using the format shown.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {variables.map((variable: EmailTemplateVariable) => (
                        <button
                          key={variable.key}
                          type="button"
                          onClick={() => insertVariable(variable.key, "body")}
                          className="group relative"
                        >
                          <Badge
                            variant="outline"
                            className="cursor-pointer hover:bg-slate-100 transition-colors font-mono text-[12px]"
                          >
                            {`{${variable.key}}`}
                          </Badge>
                          <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-slate-900 text-white text-[11px] rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                            {variable.description}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Subject Line */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label
                        htmlFor="emailSubject"
                        className="text-[13px] font-semibold text-slate-700"
                      >
                        Subject Line
                      </Label>
                      <div className="flex gap-1">
                        {variables.slice(0, 4).map((variable: EmailTemplateVariable) => (
                          <button
                            key={variable.key}
                            type="button"
                            onClick={() => insertVariable(variable.key, "subject")}
                            className="px-1.5 py-0.5 text-[10px] font-mono text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                          >
                            {`{${variable.key}}`}
                          </button>
                        ))}
                      </div>
                    </div>
                    <Input
                      ref={subjectInputRef}
                      id="emailSubject"
                      value={emailSubject}
                      onChange={(e) => setEmailSubject(e.target.value)}
                      placeholder="Enter email subject..."
                      className="h-10 border-slate-200 font-mono text-[13px]"
                    />
                  </div>

                  {/* Body */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label
                        htmlFor="emailBody"
                        className="text-[13px] font-semibold text-slate-700"
                      >
                        Email Body
                      </Label>
                      <div className="flex gap-1">
                        {variables.map((variable: EmailTemplateVariable) => (
                          <button
                            key={variable.key}
                            type="button"
                            onClick={() => insertVariable(variable.key, "body")}
                            className="px-1.5 py-0.5 text-[10px] font-mono text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors"
                          >
                            {`{${variable.key}}`}
                          </button>
                        ))}
                      </div>
                    </div>
                    <Textarea
                      ref={bodyTextareaRef}
                      id="emailBody"
                      value={emailBody}
                      onChange={(e) => setEmailBody(e.target.value)}
                      placeholder="Enter email body..."
                      rows={12}
                      className="border-slate-200 font-mono text-[13px] resize-none"
                    />
                  </div>

                  {/* Save and Reset Buttons */}
                  <div className="pt-4 border-t border-slate-100">
                    <div className="flex items-center gap-3">
                      <Button
                        onClick={handleSaveEmailTemplate}
                        disabled={updateTemplateMutation.isPending || !hasEmailChanges}
                        className={`${
                          hasEmailChanges
                            ? "bg-blue-600 hover:bg-blue-700"
                            : "bg-slate-400"
                        } text-white shadow-sm h-10 px-5`}
                      >
                        {updateTemplateMutation.isPending ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Save className="h-4 w-4 mr-2" />
                            Save Template
                          </>
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={handleResetEmailTemplate}
                        disabled={resetTemplateMutation.isPending}
                        className="h-10 border-slate-200"
                      >
                        {resetTemplateMutation.isPending ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <RotateCcw className="h-4 w-4 mr-2" />
                        )}
                        Reset to Defaults
                      </Button>
                      {saveSuccess && (
                        <span className="text-[13px] font-medium text-emerald-600">
                          Template saved successfully
                        </span>
                      )}
                      {!hasEmailChanges && !saveSuccess && (
                        <span className="text-[12px] text-slate-400">
                          No unsaved changes
                        </span>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Live Preview */}
              <Card className="border-slate-200/60 shadow-sm">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100">
                      <Eye className="h-5 w-5 text-emerald-600" />
                    </div>
                    <div>
                      <CardTitle className="text-[16px] font-semibold text-slate-900">
                        Live Preview
                      </CardTitle>
                      <CardDescription className="text-[13px] text-slate-500">
                        Preview how the email will look with sample data
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-2">
                  <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                    {/* Email Header */}
                    <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-[12px] text-slate-500 mb-1">Subject:</div>
                      <div className="text-[14px] font-medium text-slate-900">
                        {preview?.subject || emailSubject || "(No subject)"}
                      </div>
                    </div>
                    {/* Email Body */}
                    <div className="px-4 py-4">
                      <pre className="whitespace-pre-wrap font-sans text-[13px] text-slate-700 leading-relaxed">
                        {preview?.body || emailBody || "(No content)"}
                      </pre>
                    </div>
                  </div>
                  <p className="mt-3 text-[11px] text-slate-400">
                    Sample data: Product: Premium Whey Protein, Lot: LOT-2024-001, Brand: NutraFit, Reference: REF-240115-001, Customer: John Smith, Company: Health Foods Co.
                  </p>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}

      {/* Lab Mapping Tab */}
      {activeTab === "lab-mapping" && (
        <Card className="border-slate-200/60 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
                <Building2 className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <CardTitle className="text-[16px] font-semibold text-slate-900">
                  Lab Mapping
                </CardTitle>
                <CardDescription className="text-[13px] text-slate-500">
                  Read-only mapping of internal tests to Daane Labs COC methods
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {isLabMappingLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 text-[12px] text-slate-500">
                  <div className="flex flex-wrap items-center gap-3">
                    <span>Total mappings: {labMappingData?.total ?? 0}</span>
                    <span>
                      Unmapped:{" "}
                      {labMappingData?.items?.filter((item) => item.match_type === "unmapped").length ?? 0}
                    </span>
                  </div>
                  {canEditSystemSettings && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => rebuildMappingMutation.mutate()}
                      disabled={rebuildMappingMutation.isPending}
                    >
                      {rebuildMappingMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3.5 w-3.5 mr-2" />
                      )}
                      Rebuild Mappings
                    </Button>
                  )}
                </div>

                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-full text-left text-[13px]">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Test</th>
                        <th className="px-4 py-3 font-semibold">Method</th>
                        <th className="px-4 py-3 font-semibold">Daane Method</th>
                        <th className="px-4 py-3 font-semibold">Match</th>
                      </tr>
                    </thead>
                    <tbody>
                      {labMappingData?.items.map((item) => (
                        <tr key={item.lab_test_type_id} className="border-t border-slate-100">
                          <td className="px-4 py-3 text-slate-900">{item.test_name}</td>
                          <td className="px-4 py-3 text-slate-600">{item.test_method || "—"}</td>
                          <td className="px-4 py-3 text-slate-700">{item.daane_method || "—"}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                item.match_type === "name_method"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : item.match_type === "name_only"
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-slate-100 text-slate-500"
                              }`}
                              title={item.match_reason || undefined}
                            >
                              {item.match_type === "name_method"
                                ? "Name + Method"
                                : item.match_type === "name_only"
                                ? "Name Only"
                                : "Unmapped"}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {labMappingData?.items?.length === 0 && (
                        <tr>
                          <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                            No mappings found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
      </div>

      {/* Image Cropper Modal */}
      {imageToCrop && (
        <ImageCropper
          open={cropperOpen}
          onOpenChange={(open) => {
            setCropperOpen(open)
            if (!open && imageToCrop) {
              URL.revokeObjectURL(imageToCrop)
              setImageToCrop(null)
            }
          }}
          imageSrc={imageToCrop}
          onCropComplete={handleCropComplete}
          title="Crop Logo"
        />
      )}
    </div>
  )
}
