from django.db import migrations


def encrypt_existing(apps, schema_editor):
    """Chiffre les mots de passe déjà stockés en clair (préfixe absent)."""
    from projects.crypto import encrypt, is_encrypted
    ProjectCredential = apps.get_model('projects', 'ProjectCredential')
    for cred in ProjectCredential.objects.all().iterator():
        if not is_encrypted(cred.password):
            cred.password = encrypt(cred.password or "")
            cred.save(update_fields=['password'])


def decrypt_existing(apps, schema_editor):
    """Réversibilité : redéchiffre vers du clair (rollback de la migration)."""
    from projects.crypto import decrypt, is_encrypted
    ProjectCredential = apps.get_model('projects', 'ProjectCredential')
    for cred in ProjectCredential.objects.all().iterator():
        if is_encrypted(cred.password):
            cred.password = decrypt(cred.password)
            cred.save(update_fields=['password'])


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0007_task_created_by_alter_projectcredential_password'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, decrypt_existing),
    ]
