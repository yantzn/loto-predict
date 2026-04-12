data "archive_file" "fetch_placeholder" {
  type        = "zip"
  output_path = "${path.module}/fetch-placeholder.zip"

  source {
    filename = "main.py"
    content  = <<-PY
def entry_point(request):
    return ("placeholder fetch function", 200)
PY
  }

  source {
    filename = "requirements.txt"
    content  = "functions-framework==3.*\n"
  }
}

data "archive_file" "import_placeholder" {
  type        = "zip"
  output_path = "${path.module}/import-placeholder.zip"

  source {
    filename = "main.py"
    content  = <<-PY
def entry_point(request):
    return ("placeholder import function", 200)
PY
  }

  source {
    filename = "requirements.txt"
    content  = "functions-framework==3.*\n"
  }
}

data "archive_file" "notify_placeholder" {
  type        = "zip"
  output_path = "${path.module}/notify-placeholder.zip"

  source {
    filename = "main.py"
    content  = <<-PY
def entry_point(request):
    return ("placeholder notify function", 200)
PY
  }

  source {
    filename = "requirements.txt"
    content  = "functions-framework==3.*\n"
  }
}

resource "google_storage_bucket_object" "fetch_placeholder_source" {
  name         = local.function_source_objects.fetch
  bucket       = var.source_bucket_name
  source       = data.archive_file.fetch_placeholder.output_path
  content_type = "application/zip"
}

resource "google_storage_bucket_object" "import_placeholder_source" {
  name         = local.function_source_objects.import
  bucket       = var.source_bucket_name
  source       = data.archive_file.import_placeholder.output_path
  content_type = "application/zip"
}

resource "google_storage_bucket_object" "notify_placeholder_source" {
  name         = local.function_source_objects.notify
  bucket       = var.source_bucket_name
  source       = data.archive_file.notify_placeholder.output_path
  content_type = "application/zip"
}
