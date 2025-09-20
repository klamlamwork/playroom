from django.db import migrations, models
from django.utils.text import slugify

def generate_unique_slugs(apps, schema_editor):
    Event = apps.get_model('events', 'Event')
    for event in Event.objects.all():
        base_slug = slugify(event.name)
        slug = base_slug
        num = 1
        while Event.objects.filter(slug=slug).exclude(pk=event.pk).exists():
            slug = f"{base_slug}-{num}"
            num += 1
        event.slug = slug
        event.save()

class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_eventregistration'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='slug',
            field=models.SlugField(unique=True, blank=True, null=True),
        ),
        migrations.RunPython(generate_unique_slugs, reverse_code=migrations.RunPython.noop),
    ]
