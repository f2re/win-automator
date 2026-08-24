param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'WinAutomator Integration Target'
$form.Name = 'frmIntegrationTarget'
$form.Size = New-Object System.Drawing.Size(620, 470)
$form.StartPosition = 'CenterScreen'

function Add-Label([string]$Text, [int]$Y) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point(25, $Y)
    $label.Size = New-Object System.Drawing.Size(150, 25)
    $form.Controls.Add($label)
}

function Add-TextBox([string]$Name, [string]$AccessibleName, [int]$Y) {
    $control = New-Object System.Windows.Forms.TextBox
    $control.Name = $Name
    if ($AccessibleName) { $control.AccessibleName = $AccessibleName }
    $control.Location = New-Object System.Drawing.Point(190, $Y)
    $control.Size = New-Object System.Drawing.Size(360, 25)
    $form.Controls.Add($control)
    return $control
}

Add-Label 'ФИО' 30
$nameBox = Add-TextBox 'txtFullName' 'ФИО' 30

Add-Label 'Дата рождения' 80
$dateBox = Add-TextBox 'txtBirthDate' 'Дата рождения' 80

Add-Label 'Отдел' 130
$department = New-Object System.Windows.Forms.ComboBox
$department.Name = 'cmbDepartment'
$department.AccessibleName = 'Отдел'
[void]$department.Items.AddRange(@('ОП', 'ОМН', 'АЭРО'))
$department.DropDownStyle = 'DropDownList'
$department.Location = New-Object System.Drawing.Point(190, 130)
$department.Size = New-Object System.Drawing.Size(360, 25)
$form.Controls.Add($department)

# Two intentionally similar controls. The E2E test removes their stable ids from
# captured selectors so the resolver has to use semantic type + relative position.
Add-Label 'Код основной' 180
$primaryCode = Add-TextBox 'txtPrimaryCode' 'Код' 180
Add-Label 'Код дополнительный' 230
$secondaryCode = Add-TextBox 'txtSecondaryCode' 'Код' 230

$next = New-Object System.Windows.Forms.Button
$next.Name = 'btnNext'
$next.AccessibleName = 'Далее'
$next.Text = 'Далее'
$next.Location = New-Object System.Drawing.Point(440, 300)
$next.Size = New-Object System.Drawing.Size(110, 36)
$form.Controls.Add($next)

$next.Add_Click({
    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = 'WinAutomator Integration Dialog'
    $dialog.Name = 'frmIntegrationDialog'
    $dialog.Size = New-Object System.Drawing.Size(500, 240)
    $dialog.StartPosition = 'CenterParent'

    $label = New-Object System.Windows.Forms.Label
    $label.Text = 'Подтверждение'
    $label.Location = New-Object System.Drawing.Point(25, 35)
    $label.Size = New-Object System.Drawing.Size(130, 25)
    $dialog.Controls.Add($label)

    $confirm = New-Object System.Windows.Forms.TextBox
    $confirm.Name = 'txtConfirm'
    $confirm.AccessibleName = 'Подтверждение'
    $confirm.Location = New-Object System.Drawing.Point(170, 35)
    $confirm.Size = New-Object System.Drawing.Size(270, 25)
    $dialog.Controls.Add($confirm)

    $done = New-Object System.Windows.Forms.Button
    $done.Name = 'btnDone'
    $done.AccessibleName = 'Готово'
    $done.Text = 'Готово'
    $done.Location = New-Object System.Drawing.Point(330, 115)
    $done.Size = New-Object System.Drawing.Size(110, 36)
    $dialog.Controls.Add($done)

    $done.Add_Click({
        $payload = [ordered]@{
            full_name = $nameBox.Text
            birth_date = $dateBox.Text
            department = $department.Text
            primary_code = $primaryCode.Text
            secondary_code = $secondaryCode.Text
            confirm = $confirm.Text
        }
        $payload | ConvertTo-Json | Set-Content -Path $OutputPath -Encoding UTF8
        $dialog.Tag = 'done'
        $dialog.Close()
    })

    [void]$dialog.ShowDialog($form)
    if ($dialog.Tag -eq 'done') {
        $form.Close()
    }
})

[void]$form.ShowDialog()
