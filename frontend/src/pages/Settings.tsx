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
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

import { useAuthStore } from "@/store/auth"
import { useSettings, PAGE_SIZE_OPTIONS } from "@/hooks/useSettings"
import { emailTemplateApi } from "@/api/emailTemplate"
import type { EmailTemplateVariable } from "@/types/emailTemplate"

type SettingsTab = "display" | "system" | "email"

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

  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

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

  // Sync local state when settings change
  useEffect(() => {
    setStaleWarningDays(systemSettings.settings.staleWarningDays)
    setStaleCriticalDays(systemSettings.settings.staleCriticalDays)
    setRecentlyCompletedDays(systemSettings.settings.recentlyCompletedDays)
    setCompanyName(systemSettings.settings.labInfo.companyName)
    setAddress(systemSettings.settings.labInfo.address)
    setPhone(systemSettings.settings.labInfo.phone)
    setEmail(systemSettings.settings.labInfo.email)
  }, [systemSettings.settings])

  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value, 10)
    userSettings.updateSettings({ pageSize: value })
  }

  const handleSaveSystemSettings = async () => {
    setIsSaving(true)
    setSaveSuccess(false)

    // Validate thresholds
    const warning = Math.max(1, staleWarningDays)
    const critical = Math.max(warning + 1, staleCriticalDays)
    const recentlyCompleted = Math.max(1, recentlyCompletedDays)

    systemSettings.updateSettings({
      staleWarningDays: warning,
      staleCriticalDays: critical,
      recentlyCompletedDays: recentlyCompleted,
      labInfo: {
        companyName,
        address,
        phone,
        email,
        logoUrl: systemSettings.settings.labInfo.logoUrl,
      },
    })

    // Simulate async save (will be real API call later)
    await new Promise((resolve) => setTimeout(resolve, 300))

    setIsSaving(false)
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 2000)
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
    companyName !== systemSettings.settings.labInfo.companyName ||
    address !== systemSettings.settings.labInfo.address ||
    phone !== systemSettings.settings.labInfo.phone ||
    email !== systemSettings.settings.labInfo.email

  const hasEmailChanges =
    emailTemplate &&
    (emailSubject !== emailTemplate.subject || emailBody !== emailTemplate.body)

  const variables = variablesData?.variables || []

  // Tab items
  const tabs: { id: SettingsTab; label: string; icon: React.ReactNode; adminOnly?: boolean }[] = [
    { id: "display", label: "Display", icon: <Eye className="h-4 w-4" /> },
    { id: "system", label: "System", icon: <SettingsIcon className="h-4 w-4" />, adminOnly: true },
    { id: "email", label: "Customer Email", icon: <Mail className="h-4 w-4" />, adminOnly: true },
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
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Enter company name"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label
                    htmlFor="address"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Address
                  </Label>
                  <Input
                    id="address"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="Enter full address"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label
                    htmlFor="phone"
                    className="text-[13px] font-semibold text-slate-700"
                  >
                    Phone
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Enter phone number"
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
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter email address"
                    className="h-10 border-slate-200"
                  />
                </div>
                <div className="sm:col-span-2 space-y-1.5">
                  <Label className="text-[13px] font-semibold text-slate-700">
                    Company Logo
                  </Label>
                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      disabled
                      className="h-10 border-slate-200 text-slate-500"
                    >
                      <Upload className="h-4 w-4 mr-2" />
                      Upload Logo
                    </Button>
                    <span className="text-[12px] text-slate-400">
                      Coming soon - Logo upload will be available in a future update
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Save Button */}
            <div className="pt-4 border-t border-slate-100">
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleSaveSystemSettings}
                  disabled={isSaving || !hasSystemChanges}
                  className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-5"
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
                {!hasSystemChanges && !saveSuccess && (
                  <span className="text-[12px] text-slate-400">
                    No unsaved changes
                  </span>
                )}
              </div>
            </div>
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
                        className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-5"
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
      </div>
    </div>
  )
}
