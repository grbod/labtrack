/**
 * Email template types for COA email configuration.
 */

/** A single template variable definition */
export interface EmailTemplateVariable {
  key: string
  description: string
}

/** Response containing available template variables */
export interface EmailTemplateVariablesResponse {
  variables: EmailTemplateVariable[]
}

/** Email template data for updates */
export interface EmailTemplateUpdate {
  subject: string
  body: string
}

/** Email template response from API */
export interface EmailTemplate {
  id: number
  name: string
  subject: string
  body: string
  created_at: string
  updated_at: string | null
}

/** Preview of rendered email template */
export interface EmailTemplatePreview {
  subject: string
  body: string
}
