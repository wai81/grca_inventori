from django.core.management.base import BaseCommand
from inventory.roles import bootstrap_roles

class Command(BaseCommand):
    help = "Создать роли (Groups) и назначить permissions для inventory"

    def handle(self, *args, **options):
        bootstrap_roles()
        self.stdout.write(self.style.SUCCESS("Роли созданы/обновлены."))