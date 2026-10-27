from datetime import date, datetime, timedelta, timezone

FUSO_DE_SAO_PAULO = timezone(timedelta(hours=-3))


def intervalo_de_dias(inicio, fim):
    return {inicio + timedelta(days=deslocamento) for deslocamento in range((fim - inicio).days + 1)}


DIAS_SEM_EXPEDIENTE_NO_TJSP = {
    2022: intervalo_de_dias(date(2022, 1, 3), date(2022, 1, 6)) | {
        date(2022, 2, 28), date(2022, 3, 1),
        date(2022, 4, 14), date(2022, 4, 15), date(2022, 4, 21), date(2022, 4, 22),
        date(2022, 6, 16), date(2022, 6, 17),
        date(2022, 9, 7), date(2022, 10, 12), date(2022, 10, 28),
        date(2022, 11, 2), date(2022, 11, 14), date(2022, 11, 15),
        date(2022, 12, 9),
    } | intervalo_de_dias(date(2022, 12, 20), date(2022, 12, 31)),
    2023: intervalo_de_dias(date(2023, 1, 1), date(2023, 1, 6)) | {
        date(2023, 2, 20), date(2023, 2, 21),
        date(2023, 4, 6), date(2023, 4, 7), date(2023, 4, 21),
        date(2023, 5, 1), date(2023, 6, 8), date(2023, 6, 9),
        date(2023, 9, 7), date(2023, 9, 8), date(2023, 10, 12), date(2023, 10, 13),
        date(2023, 11, 2), date(2023, 11, 3), date(2023, 11, 15), date(2023, 11, 20),
        date(2023, 12, 8),
    } | intervalo_de_dias(date(2023, 12, 20), date(2023, 12, 31)),
    2024: intervalo_de_dias(date(2024, 1, 1), date(2024, 1, 6)) | {
        date(2024, 2, 12), date(2024, 2, 13),
        date(2024, 3, 28), date(2024, 3, 29),
        date(2024, 5, 1), date(2024, 5, 30), date(2024, 5, 31),
        date(2024, 7, 8), date(2024, 7, 9),
        date(2024, 10, 28), date(2024, 11, 15), date(2024, 11, 20),
    } | intervalo_de_dias(date(2024, 12, 20), date(2024, 12, 31)),
    2025: intervalo_de_dias(date(2025, 1, 1), date(2025, 1, 6)),
}


def feriados_nacionais_e_estaduais(ano):
    feriados = {
        date(ano, 1, 1), date(ano, 4, 21), date(ano, 5, 1), date(ano, 7, 9), date(ano, 9, 7),
        date(ano, 10, 12), date(ano, 11, 2), date(ano, 11, 15), date(ano, 12, 25),
    }
    if ano >= 2024:
        feriados.add(date(ano, 11, 20))
    return feriados


def esta_no_recesso_do_artigo_220(dia):
    return (dia.month == 12 and dia.day >= 20) or (dia.month == 1 and dia.day <= 20)


def eh_dia_util(dia, incluir_calendario_do_tjsp=True):
    if dia.weekday() >= 5 or dia in feriados_nacionais_e_estaduais(dia.year) or esta_no_recesso_do_artigo_220(dia):
        return False
    if incluir_calendario_do_tjsp and dia in DIAS_SEM_EXPEDIENTE_NO_TJSP.get(dia.year, set()):
        return False
    return True


def data_local(momento):
    return momento.astimezone(FUSO_DE_SAO_PAULO).date()


def contar_dias_uteis(momento_inicial, momento_final, incluir_calendario_do_tjsp=True):
    dia = data_local(momento_inicial) + timedelta(days=1)
    ultimo_dia = data_local(momento_final)
    dias_uteis = 0
    while dia <= ultimo_dia:
        if eh_dia_util(dia, incluir_calendario_do_tjsp):
            dias_uteis += 1
        dia += timedelta(days=1)
    return dias_uteis
