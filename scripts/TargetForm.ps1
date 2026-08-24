Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Карточка сотрудника — тест Win Automator'
$form.Size = New-Object System.Drawing.Size(560,360)
$form.StartPosition = 'CenterScreen'

$labels = @('ФИО','Дата рождения','Отдел','Должность')
$y = 30
$controls = @{}
foreach ($labelText in $labels) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $labelText
    $label.Location = New-Object System.Drawing.Point(25,$y)
    $label.Size = New-Object System.Drawing.Size(120,25)
    $form.Controls.Add($label)

    if ($labelText -eq 'Отдел') {
        $control = New-Object System.Windows.Forms.ComboBox
        [void]$control.Items.AddRange(@('ОП','ОМН','АЭРО'))
        $control.DropDownStyle = 'DropDownList'
    } else {
        $control = New-Object System.Windows.Forms.TextBox
    }
    $control.Name = switch ($labelText) {
        'ФИО' {'txtFullName'}
        'Дата рождения' {'txtBirthDate'}
        'Отдел' {'cmbDepartment'}
        'Должность' {'txtPosition'}
    }
    $control.AccessibleName = $labelText
    $control.Location = New-Object System.Drawing.Point(160,$y)
    $control.Size = New-Object System.Drawing.Size(340,25)
    $form.Controls.Add($control)
    $controls[$labelText] = $control
    $y += 55
}

$save = New-Object System.Windows.Forms.Button
$save.Name = 'btnSave'
$save.AccessibleName = 'Сохранить'
$save.Text = 'Сохранить'
$save.Location = New-Object System.Drawing.Point(390,260)
$save.Size = New-Object System.Drawing.Size(110,35)
$save.Add_Click({
    $msg = "ФИО: $($controls['ФИО'].Text)`nДата: $($controls['Дата рождения'].Text)`nОтдел: $($controls['Отдел'].Text)`nДолжность: $($controls['Должность'].Text)"
    [System.Windows.Forms.MessageBox]::Show($msg, 'Запись сохранена') | Out-Null
})
$form.Controls.Add($save)

[void]$form.ShowDialog()
