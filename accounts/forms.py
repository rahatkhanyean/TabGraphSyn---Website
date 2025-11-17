from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={'autocomplete': 'username', 'class': 'input-control', 'placeholder': 'jane.doe'}
        ),
        label='Username',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'current-password',
                'class': 'input-control',
                'placeholder': '********',
            }
        ),
        label='Password',
    )


class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={'autocomplete': 'username', 'class': 'input-control', 'placeholder': 'new.user'}
        ),
        label='Username',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'autocomplete': 'new-password',
                'class': 'input-control',
                'placeholder': '********',
            }
        ),
        label='Password',
        min_length=6,
    )
