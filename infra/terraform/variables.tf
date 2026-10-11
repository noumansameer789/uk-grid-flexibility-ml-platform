variable "subscription_id" {
  description = "Azure subscription authorised for this deployment"
  type        = string
}
variable "location" {
  type    = string
  default = "uksouth"
}
variable "name" {
  type    = string
  default = "gridflex"
}
variable "container_image" {
  description = "Public GHCR image pinned to a content digest"
  type        = string
  validation {
    condition     = can(regex("^ghcr\\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$", var.container_image))
    error_message = "Use a published public GHCR image pinned to its sha256 digest. Tags are mutable."
  }
}
variable "alert_email" {
  description = "Optional operator email for Azure log alerts; blank disables email routing"
  type        = string
  default     = ""
}
