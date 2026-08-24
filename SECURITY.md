# Security Policy

## Supported versions

На стадии до 1.0 security fixes выпускаются для последней опубликованной версии.

## Reporting

Не публикуйте в issue:
- пароли, токены, персональные данные;
- реальные закрытые Excel-файлы;
- сведения, позволяющие атаковать конкретную внутреннюю систему.

Для чувствительных сообщений используйте GitHub Security Advisory / private vulnerability reporting репозитория, если этот канал доступен. Если он недоступен, свяжитесь с владельцем репозитория через профиль GitHub и передайте только минимальную информацию для установления безопасного канала.

Для обычных ошибок без чувствительных данных используйте Bug Report template.

## Release integrity

Официальными считаются assets в GitHub Releases этого репозитория. Для них публикуется `SHA256SUMS.txt`, а release workflow создает GitHub build provenance attestation.
