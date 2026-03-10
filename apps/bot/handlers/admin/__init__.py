from aiogram import Router


def register_admin_handlers(router: Router):
    from . import departments, employees, common, movements, devices

    router.include_router(departments.router)
    router.include_router(employees.router)
    router.include_router(movements.router)
    router.include_router(devices.router)
    router.include_router(common.router)