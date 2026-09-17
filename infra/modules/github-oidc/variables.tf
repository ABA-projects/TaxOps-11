variable "github_repo" {
  description = "owner/repo autorizado a asumir el rol vía OIDC"
  type        = string
  default     = "ABA-projects/TaxOps-11"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "tfstate_bucket" {
  type        = string
  description = "Bucket del state (backend.tf). El rol de plan necesita escribir el .tflock ahí."
  default     = "taxops11-tfstate-786567028012"
}

variable "tfstate_key" {
  type    = string
  default = "prod/terraform.tfstate"
}

variable "ecr_repository" {
  type    = string
  default = "taxops-api"
}

variable "lambda_functions" {
  type        = list(string)
  description = "Funciones que deploy-lambda.yml actualiza con update-function-code."
  default     = ["taxops-api-prod", "taxops-worker-prod"]
}

variable "job_artifacts_bucket" {
  type    = string
  default = "taxops-job-artifacts-prod"
}
