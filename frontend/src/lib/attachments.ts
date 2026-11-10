export const FILE_SIZE_LIMIT = 3 * 1024 * 1024;
export const FILE_ACCEPT =
  ".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,image/png,image/jpeg,application/pdf";
export const FILE_FORMATS = "PDF, DOCX, TXT, MD, CSV, PNG и JPEG";

export function fileError(file: File) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!FILE_ACCEPT.split(",").includes(`.${extension}`)) return `Поддерживаются ${FILE_FORMATS}.`;
  if (!file.size || file.size > FILE_SIZE_LIMIT)
    return "Размер файла должен быть от 1 байта до 3 МБ.";
  return "";
}

export function formatFileSize(size: number) {
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} КБ`;
  return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
}
