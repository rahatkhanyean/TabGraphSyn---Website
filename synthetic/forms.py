from __future__ import annotations

from django import forms
from django.utils.safestring import mark_safe

class SyntheticDataForm(forms.Form):
    DATA_SOURCE_CHOICES = [
        (
            'preloaded', 
            mark_safe(
                'Package Dataset<br><span class="help-text">'
                'Generate synthetic patients from benchmark datasets.'
                '</span>'
            ),
        ),
        (
            'uploaded',
            mark_safe(
                'Upload CSV<br><span class="help-text">'
                'Uploading a CSV automatically profiles column kinds and suggested representations.'
                '</span>'
            ),
        ),
    ]
    METADATA_MODE_CHOICES = [
        ('template', 'Use existing metadata'),
        ('custom', 'Custom metadata'),
    ]

    data_source = forms.ChoiceField(
        label='Data source',
        choices=DATA_SOURCE_CHOICES,
        initial='preloaded',
        widget=forms.RadioSelect,
    )
    dataset = forms.ChoiceField(
        label='Dataset',
        required=False,
        widget=forms.Select(attrs={'class': 'input-control'}),
    )
    staging_token = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    metadata_mode = forms.ChoiceField(
        label='Metadata option',
        required=False,
        choices=METADATA_MODE_CHOICES,
        widget=forms.RadioSelect,
    )
    metadata_template = forms.ChoiceField(
        label='Metadata template',
        required=False,
        widget=forms.Select(attrs={'class': 'input-control'}),
    )
    uploaded_dataset_name = forms.CharField(
        label='Dataset name',
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'e.g. customer_orders'}),
    )
    uploaded_table_name = forms.CharField(
        label='Table name',
        required=False,
        widget=forms.TextInput(attrs={'class': 'input-control', 'placeholder': 'e.g. orders'}),
    )
    epochs_vae = forms.IntegerField(
        label='VAE epochs',
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'input-control', 'min': 1}),
    )
    epochs_gnn = forms.IntegerField(
        label='GNN epochs',
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'input-control', 'min': 1}),
    )
    epochs_diff = forms.IntegerField(
        label='Diffusion epochs',
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'input-control', 'min': 1}),
    )
    enable_epoch_eval = forms.BooleanField(
        label='Enable epoch-wise evaluation',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox-control'}),
        help_text='Track Marginal Distribution Error and Pairwise Correlation Error during training',
    )
    eval_frequency = forms.IntegerField(
        label='Evaluation frequency (epochs)',
        min_value=1,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'input-control', 'min': 1}),
        help_text='Evaluate every N epochs (default: 10)',
    )
    eval_samples = forms.IntegerField(
        label='Evaluation samples',
        min_value=100,
        initial=500,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'input-control', 'min': 100}),
        help_text='Number of synthetic samples to generate per evaluation (default: 500)',
    )

    def __init__(self, *args, dataset_choices: list[tuple[str, str]] | None = None, metadata_templates: list[tuple[str, str]] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if dataset_choices:
            self.fields['dataset'].choices = dataset_choices
            self.fields['dataset'].initial = dataset_choices[0][0]
        if metadata_templates:
            self.fields['metadata_template'].choices = metadata_templates
            self.fields['metadata_template'].initial = metadata_templates[0][0]
        else:
            self.fields['metadata_template'].choices = []

    def clean(self) -> dict:
        cleaned = super().clean()
        data_source = cleaned.get('data_source')
        dataset = cleaned.get('dataset')
        staging_token = cleaned.get('staging_token')
        metadata_mode = cleaned.get('metadata_mode')
        metadata_template = cleaned.get('metadata_template')

        if data_source == 'preloaded':
            if not dataset:
                self.add_error('dataset', 'Select a dataset to continue.')
            cleaned['metadata_mode'] = 'template'
            if not metadata_template:
                cleaned['metadata_template'] = dataset
        elif data_source == 'uploaded':
            if not staging_token:
                self.add_error(None, 'Upload a dataset before running the pipeline.')
            if metadata_mode not in {'template', 'custom'}:
                self.add_error('metadata_mode', 'Choose how metadata should be provided.')
            if metadata_mode == 'template' and not metadata_template:
                self.add_error('metadata_template', 'Select a metadata template.')
        else:
            self.add_error('data_source', 'Unsupported data source.')
        return cleaned
